#!/usr/bin/env python3
"""
acs convention checker — self-contained (Python stdlib only).

/acs:init copies this file into the consumer repo at `.acs/ci/check-conventions.py`
and wires it into a GitHub Actions workflow (and, optionally, a local pre-push
hook). It enforces that branch names, PR titles, PR descriptions, labels, and
commit messages match the *same* format strings the acs pipeline renders from
(`formats.*` in `.acs/settings.json`) — so a hand-made PR that never went through
`/acs:create-pr` is held to the identical convention before it can merge.

No acs plugin install is required on the runner: the formats and ticket prefix
are read from the committed `.acs/settings.json`. The check is FAIL-CLOSED — if
no settings with `ticket_prefix` + `formats` are found, it errors and tells the
user to run `/acs:init`.

Modes:
  --mode pr        CI: validate a pull request (branch, title, body, labels,
                   commit subjects). Inputs come from ACS_PR_* env vars set by
                   the workflow from the `pull_request` event payload.
  --mode pre-push  local git hook: validate the branch name + commit subjects of
                   the range being pushed (PR title/body/labels do not exist yet,
                   so those checks are CI's job).

Exit code 0 = conforms or exempt; 1 = one or more violations (or fail-closed).
"""

import fnmatch
import json
import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Defaults — mirror plugins/acs/schemas/settings.schema.json. Used only when a
# key is absent from the merged settings, so behaviour is predictable even on a
# repo initialised by an older acs that has no `enforcement` block yet.
# ---------------------------------------------------------------------------

FORMAT_DEFAULTS = {
    "branch_name": "{type}/{ticket_id}-{slug}",
    "commit_message": "{ticket_id} {summary}",
    "pr_title": "[{ticket_id}] {title}",
}

CHECK_DEFAULTS = {
    "branch_name": True,
    "pr_title": True,
    "pr_description": True,
    "acs_label": True,
    "commit_message": False,  # noisy under squash-merge; init turns it on per repo
}

ENFORCEMENT_DEFAULTS = {
    "exempt_branches": ["release/*", "dependabot/*", "renovate/*"],
    "exempt_label": "acs-exempt",
    "require_label": "ACS",
    "pr_description_sections": ["Summary", "Ticket", "Changes", "Test plan"],
}

TICKET_TYPES = ("epic", "story", "task")

# Free-text placeholders compile to "one or more characters". {ticket_id} and
# {type} and {slug} get exact shapes below.
FREE_TEXT_TOKENS = {"title", "summary", "external_key"}


# ---------------------------------------------------------------------------
# Settings loading (precedence local > project > user; CI only sees project)
# ---------------------------------------------------------------------------

def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write("warning: unreadable settings at %s (%s) — ignored\n" % (path, exc))
        return None


def _deep_merge(base, override):
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
    return base


def load_settings(repo_root):
    """Merge user -> project -> local (most specific wins). Returns (settings, sources)."""
    candidates = [
        os.path.expanduser("~/.acs/settings.json"),
        os.path.join(repo_root, ".acs", "settings.json"),
        os.path.join(repo_root, ".acs", "settings.local.json"),
    ]
    settings, sources = {}, []
    for path in candidates:
        data = _read_json(path)
        if isinstance(data, dict):
            _deep_merge(settings, data)
            sources.append(path)
    return settings, sources


# ---------------------------------------------------------------------------
# Format string -> regex (mirrors acs render_format token vocabulary)
# ---------------------------------------------------------------------------

def format_to_regex(template, ticket_prefix):
    """Compile a `{placeholder}` format string into an anchored regex.

    Literal text is escaped; {ticket_id} becomes `<PREFIX>-<n>`, {type} the
    ticket-type alternation, {slug} a lower-kebab token, and free-text tokens
    ({title}, {summary}, {external_key}) become `.+` (non-empty).
    """
    parts, idx = ["^"], 0
    for m in re.finditer(r"\{([a-z_]+)\}", template):
        parts.append(re.escape(template[idx:m.start()]))
        token = m.group(1)
        if token == "ticket_id":
            parts.append(r"%s-\d+" % re.escape(ticket_prefix))
        elif token == "type":
            parts.append(r"(?:%s)" % "|".join(TICKET_TYPES))
        elif token == "slug":
            parts.append(r"[a-z0-9]+(?:-[a-z0-9]+)*")
        else:  # free text (and any unknown token, which settings validation rejects upstream)
            parts.append(r".+")
        idx = m.end()
    parts.append(re.escape(template[idx:]))
    parts.append("$")
    return re.compile("".join(parts))


# ---------------------------------------------------------------------------
# Pure evaluation core (unit-tested; no I/O)
# ---------------------------------------------------------------------------

class Result:
    def __init__(self):
        self.errors = []      # list of (heading, detail)
        self.skipped = []     # checks disabled in settings
        self.exempt = None    # reason string when the PR/branch is exempt

    @property
    def passed(self):
        return not self.errors


def _enabled(settings, check):
    checks = (settings.get("enforcement") or {}).get("checks") or {}
    return bool(checks.get(check, CHECK_DEFAULTS[check]))


def _enf(settings, key):
    return (settings.get("enforcement") or {}).get(key, ENFORCEMENT_DEFAULTS[key])


def _fmt(settings, key):
    return (settings.get("formats") or {}).get(key, FORMAT_DEFAULTS[key])


def is_exempt(settings, branch, labels):
    """Return an exemption reason string, or None."""
    exempt_label = _enf(settings, "exempt_label")
    if exempt_label and exempt_label in (labels or []):
        return "label '%s' present" % exempt_label
    for pattern in _enf(settings, "exempt_branches") or []:
        if branch and fnmatch.fnmatch(branch, pattern):
            return "branch matches exempt pattern '%s'" % pattern
    return None


def evaluate(settings, ctx, mode):
    """ctx keys: branch, title, body, labels (list), commit_subjects (list).

    mode 'pr' runs every enabled check; 'pre-push' runs only branch + commits
    (title/body/labels are unknown before the PR exists).
    """
    res = Result()
    prefix = settings.get("ticket_prefix")
    if not prefix or not isinstance(settings.get("formats"), dict):
        res.errors.append((
            "settings",
            "no committed acs conventions found (ticket_prefix + formats). "
            "Run /acs:init and commit .acs/settings.json.",
        ))
        return res

    branch = (ctx.get("branch") or "").strip()
    labels = ctx.get("labels") or []

    res.exempt = is_exempt(settings, branch, labels)
    if res.exempt:
        return res

    # Branch name -----------------------------------------------------------
    if _enabled(settings, "branch_name"):
        template = _fmt(settings, "branch_name")
        if not branch:
            res.errors.append(("branch_name", "could not determine the branch name"))
        elif not format_to_regex(template, prefix).match(branch):
            res.errors.append((
                "branch_name",
                "branch '%s' does not match required format '%s' "
                "(e.g. %s)" % (branch, template, _example(template, prefix)),
            ))
    else:
        res.skipped.append("branch_name")

    # Commit messages -------------------------------------------------------
    if _enabled(settings, "commit_message"):
        template = _fmt(settings, "commit_message")
        rx = format_to_regex(template, prefix)
        bad = [s for s in (ctx.get("commit_subjects") or [])
               if not _is_ignorable_commit(s) and not rx.match(s.strip())]
        for subject in bad:
            res.errors.append((
                "commit_message",
                "commit subject %r does not match required format '%s'" % (subject, template),
            ))
    else:
        res.skipped.append("commit_message")

    if mode == "pre-push":
        return res  # title/body/labels don't exist yet

    # PR title --------------------------------------------------------------
    if _enabled(settings, "pr_title"):
        template = _fmt(settings, "pr_title")
        title = (ctx.get("title") or "").strip()
        if not title:
            res.errors.append(("pr_title", "PR has no title"))
        elif not format_to_regex(template, prefix).match(title):
            res.errors.append((
                "pr_title",
                "PR title '%s' does not match required format '%s' "
                "(e.g. %s)" % (title, template, _example(template, prefix)),
            ))
    else:
        res.skipped.append("pr_title")

    # ACS label -------------------------------------------------------------
    if _enabled(settings, "acs_label"):
        required = _enf(settings, "require_label")
        if required and required not in labels:
            res.errors.append((
                "acs_label",
                "PR is missing the required '%s' label (added by /acs:create-pr). "
                "Apply it, or add the '%s' label to exempt a non-ticket PR."
                % (required, _enf(settings, "exempt_label")),
            ))
    else:
        res.skipped.append("acs_label")

    # PR description --------------------------------------------------------
    if _enabled(settings, "pr_description"):
        body = ctx.get("body") or ""
        for section in _enf(settings, "pr_description_sections") or []:
            if not _has_heading(body, section):
                res.errors.append((
                    "pr_description",
                    "PR description is missing a '## %s' section" % section,
                ))
    else:
        res.skipped.append("pr_description")

    return res


def _is_ignorable_commit(subject):
    s = (subject or "").strip()
    return s.startswith("Merge ") or s.startswith("Revert ") or s.startswith("fixup!") or s.startswith("squash!")


def _has_heading(body, section):
    pattern = re.compile(r"^#{1,6}\s*%s\s*:?\s*$" % re.escape(section), re.IGNORECASE | re.MULTILINE)
    return bool(pattern.search(body or ""))


def _example(template, prefix):
    return (template
            .replace("{ticket_id}", "%s-12" % prefix)
            .replace("{type}", "task")
            .replace("{slug}", "short-description")
            .replace("{title}", "Short description")
            .replace("{summary}", "short description")
            .replace("{external_key}", ""))


# ---------------------------------------------------------------------------
# I/O glue (git, env, annotations)
# ---------------------------------------------------------------------------

def _git(args, cwd):
    try:
        out = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
        return out.stdout if out.returncode == 0 else None
    except OSError:
        return None


def _commit_subjects_pr(repo_root, base_ref):
    if not base_ref:
        return []
    for rng in ("origin/%s..HEAD" % base_ref, "%s..HEAD" % base_ref):
        out = _git(["log", "--no-merges", "--format=%s", rng], repo_root)
        if out is not None:
            return [line for line in out.splitlines() if line.strip()]
    sys.stderr.write("warning: could not compute commit range against '%s' — "
                     "commit-message check skipped (need fetch-depth: 0)\n" % base_ref)
    return []


def _commit_subjects_prepush(repo_root):
    """Parse git's pre-push stdin (`<localref> <localsha> <remoteref> <remotesha>`)."""
    zero = "0" * 40
    subjects, saw_stdin = [], False
    for line in sys.stdin.read().splitlines():
        saw_stdin = True
        parts = line.split()
        if len(parts) != 4:
            continue
        _, local_sha, _, remote_sha = parts
        if local_sha.startswith("0000000"):  # branch deletion
            continue
        rng = local_sha if remote_sha.startswith("0000000") else "%s..%s" % (remote_sha, local_sha)
        out = _git(["log", "--no-merges", "--format=%s", rng], repo_root)
        if out:
            subjects.extend(s for s in out.splitlines() if s.strip())
    if not saw_stdin:  # invoked manually, not by git — fall back to upstream range
        out = _git(["log", "--no-merges", "--format=%s", "@{u}..HEAD"], repo_root)
        if out:
            subjects.extend(s for s in out.splitlines() if s.strip())
    return subjects


def _env_labels():
    raw = (os.environ.get("ACS_PR_LABELS", "") or "").strip()
    if raw.startswith("["):  # JSON array from `toJSON(...labels.*.name)`
        try:
            return [str(l).strip() for l in json.loads(raw) if str(l).strip()]
        except json.JSONDecodeError:
            pass
    return [l.strip() for l in re.split(r"[\n,]", raw) if l.strip()]


def _emit(res, mode):
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    if res.exempt:
        print("acs conventions: PR exempt (%s) — checks skipped." % res.exempt)
        return 0
    if res.passed:
        skipped = (" (skipped: %s)" % ", ".join(res.skipped)) if res.skipped else ""
        print("acs conventions: all checks passed.%s" % skipped)
        return 0
    summary = "acs conventions: %d violation(s) found.\n" % len(res.errors)
    (print(summary) if in_actions else sys.stderr.write(summary + "\n"))
    for heading, detail in res.errors:
        if in_actions:
            print("::error title=acs convention (%s)::%s" % (heading, detail))
        else:
            sys.stderr.write("  ✗ [%s] %s\n" % (heading, detail))
    if not in_actions:
        sys.stderr.write(
            "\nFix the above, or add the exempt label for a legitimate non-ticket PR.\n"
            "These conventions come from .acs/settings.json — run /acs:init to change them.\n")
    return 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "pr"
    repo_root = "."
    while argv:
        arg = argv.pop(0)
        if arg == "--mode":
            mode = argv.pop(0)
        elif arg == "--repo-root":
            repo_root = argv.pop(0)
        elif arg in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            sys.stderr.write("unknown argument: %s\n" % arg)
            return 2
    if mode not in ("pr", "pre-push"):
        sys.stderr.write("invalid --mode %r (expected 'pr' or 'pre-push')\n" % mode)
        return 2

    repo_root = _git(["rev-parse", "--show-toplevel"], repo_root)
    repo_root = repo_root.strip() if repo_root else "."

    settings, _ = load_settings(repo_root)

    if mode == "pre-push":
        ctx = {
            "branch": (_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root) or "").strip(),
            "commit_subjects": _commit_subjects_prepush(repo_root),
        }
    else:
        ctx = {
            "branch": os.environ.get("ACS_PR_BRANCH", ""),
            "title": os.environ.get("ACS_PR_TITLE", ""),
            "body": os.environ.get("ACS_PR_BODY", ""),
            "labels": _env_labels(),
            "commit_subjects": _commit_subjects_pr(repo_root, os.environ.get("ACS_BASE_REF", "")),
        }

    res = evaluate(settings, ctx, mode)
    return _emit(res, mode)


if __name__ == "__main__":
    sys.exit(main())
