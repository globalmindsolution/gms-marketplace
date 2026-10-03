#!/usr/bin/env python3
"""
acs convention check — self-contained (Python stdlib only).

/acs:setup copies this file into the consumer repo at `.acs/ci/check-conventions.py`
and wires it into a GitHub Actions workflow.

It checks ONE thing: that the PR description names its ticket -- the acs id
(`ACS-12`), a `#<n>` issue reference, or an issue link (ADR-0106). The
description is where a PR is linked to its ticket (ADR-0105); branch names,
titles and commit subjects are free, and no label is required.

No acs plugin install is required on the runner. The only setting read is
`ticket_prefix` from the committed `.acs/settings.json` (default `ACS`, ADR-0105),
so a repo with no settings file at all is checked against the default. A
settings file that is present but malformed fails the check.

A PR labelled `acs-exempt`, or from a `release/*`, `dependabot/*` or `renovate/*`
branch, is skipped. These exemptions are fixed; acs_lib.conventions holds the
same values and a test keeps the two in step.

Inputs come from ACS_PR_* env vars set by the workflow from the `pull_request`
event payload. Exit code 0 = names a ticket or exempt; 1 = it does not (or
fail-closed on a malformed settings file).
"""

import fnmatch
import json
import os
import re
import sys

DEFAULT_TICKET_PREFIX = "ACS"

#: Mirrors acs_lib.conventions.
EXEMPT_BRANCHES = ("release/*", "dependabot/*", "renovate/*")
EXEMPT_LABEL = "acs-exempt"

#: The CI check, the ticket link, is the only one. Kept as a table so a caller
#: (pr-conventions.py) can name the mode it drives.
MODE_CHECKS = {"pr": ["ticket_link"]}


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write("warning: unreadable settings at %s (%s) — ignored\n" % (path, exc))
        return None


def load_settings(repo_root):
    """Merge user -> project -> local (most specific wins). CI sees only project."""
    candidates = [
        os.path.expanduser("~/.acs/settings.json"),
        os.path.join(repo_root, ".acs", "settings.json"),
        os.path.join(repo_root, ".acs", "settings.local.json"),
    ]
    settings, sources = {}, []
    for path in candidates:
        data = _read_json(path)
        if isinstance(data, dict):
            settings.update(data)
            sources.append(path)
    return settings, sources


class Result:
    def __init__(self):
        self.errors = []      # list of (heading, detail)
        self.skipped = []
        self.exempt = None    # reason string when the PR is exempt

    @property
    def passed(self):
        return not self.errors


def is_exempt(settings, branch, labels):
    """Return an exemption reason string, or None."""
    if EXEMPT_LABEL in (labels or []):
        return "label '%s' present" % EXEMPT_LABEL
    for pattern in EXEMPT_BRANCHES:
        if branch and fnmatch.fnmatch(branch, pattern):
            return "branch matches exempt pattern '%s'" % pattern
    return None


def ticket_link_re(prefix):
    """What names a ticket in a PR description: its acs id (`ACS-12`), a
    `#<n>` issue reference, or a link to an issue."""
    return re.compile(r"\b%s-\d+\b|(?<![\w/&])#\d+\b|/issues/\d+\b" % re.escape(prefix))


def _check_ticket_link(settings, ctx, prefix, res):
    if not ticket_link_re(prefix).search(ctx.get("body") or ""):
        res.errors.append(("ticket_link",
            "PR description names no ticket: add its id (e.g. %s-12), a #<issue> "
            "reference or an issue link." % prefix))


_CHECKERS = {"ticket_link": _check_ticket_link}


def evaluate(settings, ctx, mode="pr"):
    """ctx keys: branch, body, labels (list)."""
    res = Result()
    prefix = settings.get("ticket_prefix", DEFAULT_TICKET_PREFIX)
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*", prefix):
        res.errors.append((
            "settings",
            "malformed ticket_prefix in .acs/settings.json: it must be an uppercase "
            "identifier (remove it to use the default).",
        ))
        return res

    res.exempt = is_exempt(settings, (ctx.get("branch") or "").strip(), ctx.get("labels") or [])
    if res.exempt:
        return res

    for check in MODE_CHECKS.get(mode, []):
        _CHECKERS[check](settings, ctx, prefix, res)
    return res


def _env_labels():
    raw = (os.environ.get("ACS_PR_LABELS", "") or "").strip()
    if raw.startswith("["):  # JSON array from `toJSON(...labels.*.name)`
        try:
            return [str(l).strip() for l in json.loads(raw) if str(l).strip()]
        except json.JSONDecodeError:
            pass
    return [l.strip() for l in re.split(r"[\n,]", raw) if l.strip()]


def _emit(res):
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    if res.exempt:
        print("acs conventions: exempt (%s) — checks skipped." % res.exempt)
        return 0
    if res.passed:
        print("acs conventions: the PR names its ticket.")
        return 0
    summary = "acs conventions: %d violation(s) found.\n" % len(res.errors)
    (print(summary) if in_actions else sys.stderr.write(summary + "\n"))
    for heading, detail in res.errors:
        if in_actions:
            print("::error title=acs convention (%s)::%s" % (heading, detail))
        else:
            sys.stderr.write("  ✗ [%s] %s\n" % (heading, detail))
    if not in_actions:
        sys.stderr.write("\nFix the above, or add the '%s' label for a legitimate "
                         "non-ticket PR.\n" % EXEMPT_LABEL)
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
    if mode != "pr":
        sys.stderr.write("invalid --mode %r (the only mode is 'pr')\n" % mode)
        return 2

    settings, _ = load_settings(repo_root)
    # The branch and labels only decide an exemption; the body is checked.
    ctx = {
        "branch": os.environ.get("ACS_PR_BRANCH", ""),
        "body": os.environ.get("ACS_PR_BODY", ""),
        "labels": _env_labels(),
    }
    return _emit(evaluate(settings, ctx, mode))


if __name__ == "__main__":
    sys.exit(main())
