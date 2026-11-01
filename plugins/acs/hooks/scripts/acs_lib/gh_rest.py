"""acs_lib.gh_rest — every GitHub call acs makes, through `gh api` REST (ADR-0149).

gh's porcelain -- `gh pr list/view/create/edit/checks/diff/merge`, `gh issue
view/create/edit`, `gh repo view`, `gh label list` -- runs on GitHub's GraphQL
API, and a Claude Code session refuses GraphQL outright (HTTP 403 "GitHub
GraphQL is not available from Claude Code sessions"). Each porcelain call was a
stop waiting for the first run in such a session: /acs:release's open-PR probe
died on `gh pr list` before it read a single file.

`gh api` against a REST endpoint works in every environment `gh` does, so this
module is the one place acs talks to GitHub: argv builders for the writes, and
readers that reshape REST answers into the documents the callers already
consumed from `gh pr view --json` (camelCase keys, GraphQL enum spellings), so
`readiness.merge_readiness` and every recorded fixture keep their meaning.
`gh` is still the only transport (ADR-0088); only the endpoint family changed.

Endpoints use gh's `{owner}/{repo}` placeholders, which gh fills from the git
remote of the working directory -- the same repository the porcelain resolved.

The one exception is Projects v2 (`gh project …`): it has no REST surface gh
can drive, so those calls stay GraphQL and stay non-critical (forge.py), which
`tests/acs/test_gh_rest_only.py` allows by name and nothing else.
"""

import json
import subprocess
from urllib.parse import quote

#: The endpoint prefix for the repository gh resolves from the working directory.
REPO = "repos/{owner}/{repo}"

#: What `run` answers when there is no gh binary to run.
NOT_ON_PATH = "gh is not on PATH"

#: REST `mergeable` -> the GraphQL MergeableState the readiness table reads.
_MERGEABLE = {True: "MERGEABLE", False: "CONFLICTING", None: "UNKNOWN"}

#: Review states that decide a reviewer's standing; COMMENTED and PENDING do not.
_DECIDING_REVIEWS = ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")


class GhError(Exception):
    """A REST read that did not answer. `detail` carries gh's own words."""

    def __init__(self, what, detail):
        Exception.__init__(self, "%s: %s" % (what, detail))
        self.what = what
        self.detail = detail


def run(argv, cwd=None, timeout=None):
    """The default runner: (returncode, stdout, stderr), 127 when gh is absent."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=cwd,
                              timeout=timeout)
    except FileNotFoundError:
        return 127, "", NOT_ON_PATH
    except OSError as exc:
        return 126, "", "gh could not be run (%s)" % exc
    return proc.returncode, proc.stdout, proc.stderr


def api(endpoint, *args):
    """`gh api <endpoint> …` as argv."""
    return ["gh", "api", endpoint] + [str(a) for a in args]


def _fields(flag, name, values):
    out = []
    for value in values:
        out += [flag, "%s[]=%s" % (name, value)]
    return out


# ---------------------------------------------------------------------------
# Writes, as argv
# ---------------------------------------------------------------------------

def label_create(name, description):
    """Create a label. Exits non-zero when it already exists: callers ignore that."""
    return api(REPO + "/labels", "-X", "POST", "-f", "name=" + name,
               "-f", "description=" + description)


def issue_create(title, body_file):
    """Create an issue; stdout is its html_url, as `gh issue create` printed."""
    return api(REPO + "/issues", "-X", "POST", "-f", "title=" + title,
               "-F", "body=@" + body_file, "--jq", ".html_url")


def issue_edit_body(number, body_file):
    return api("%s/issues/%s" % (REPO, number), "-X", "PATCH", "-F", "body=@" + body_file)


def issue_set_milestone(number, milestone_number):
    return api("%s/issues/%s" % (REPO, number), "-X", "PATCH",
               "-F", "milestone=%s" % milestone_number)


def add_labels(number, labels):
    """Labels on an issue or a PR (a PR is an issue to this endpoint)."""
    return api("%s/issues/%s/labels" % (REPO, number), "-X", "POST",
               *_fields("-f", "labels", labels))


def add_assignees(number, logins):
    return api("%s/issues/%s/assignees" % (REPO, number), "-X", "POST",
               *_fields("-f", "assignees", logins))


def request_reviewers(number, owners):
    """Request review from users and `@org/team` handles (team -> its slug)."""
    users = [o.lstrip("@") for o in owners if "/" not in o]
    teams = [o.lstrip("@").split("/", 1)[1] for o in owners if "/" in o]
    return api("%s/pulls/%s/requested_reviewers" % (REPO, number), "-X", "POST",
               *(_fields("-f", "reviewers", users) + _fields("-f", "team_reviewers", teams)))


def pr_create(base, head, title, body_file, draft=False):
    """Open a PR; stdout is the created PR as JSON."""
    argv = api(REPO + "/pulls", "-X", "POST", "-f", "base=" + base, "-f", "head=" + head,
               "-f", "title=" + title, "-F", "body=@" + body_file)
    if draft:
        argv += ["-F", "draft=true"]
    return argv


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

def user_login():
    return api("user", "--jq", ".login")


def issue_view(number):
    return api("%s/issues/%s" % (REPO, number))


def pr_url(number):
    return api("%s/pulls/%s" % (REPO, number), "--jq", ".html_url")


def pr_files(number):
    """The PR's changed paths, one per line, as `gh pr diff --name-only` printed."""
    return api("%s/pulls/%s/files?per_page=100" % (REPO, number), "--paginate",
               "--jq", ".[].filename")


def milestones():
    return api(REPO + "/milestones?state=all&per_page=100", "--paginate", "--jq", ".[]")


def pr_list(head, state="open"):
    """PRs whose head is `head` in this repository. `state` is open|closed|all."""
    return api("%s/pulls?head={owner}:%s&state=%s&per_page=100"
               % (REPO, quote(head, safe="/"), state))


def _call(gh, argv, what):
    code, out, err = gh(argv)
    if code != 0:
        raise GhError(what, (err or out or "").strip() or "gh api exited %d" % code)
    return out


def _json(gh, argv, what):
    out = _call(gh, argv, what)
    try:
        return json.loads(out or "")
    except ValueError:
        raise GhError(what, "gh api returned output that is not JSON")


def _json_lines(gh, argv, what):
    """A `--jq '.[]'`-style answer: one JSON value per line."""
    rows = []
    for line in (_call(gh, argv, what) or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            raise GhError(what, "gh api returned a line that is not JSON")
    return rows


def pr_state(raw):
    """OPEN | CLOSED | MERGED, from a REST pull."""
    if raw.get("merged_at") or raw.get("merged") is True:
        return "MERGED"
    return str(raw.get("state") or "").upper()


def pr_row(raw):
    """A REST pull as the `gh pr list/view --json` row callers read."""
    return {
        "number": raw.get("number"),
        "url": raw.get("html_url"),
        "state": pr_state(raw),
        "isDraft": raw.get("draft") is True,
        "headRefName": (raw.get("head") or {}).get("ref"),
        "baseRefName": (raw.get("base") or {}).get("ref"),
        "labels": [{"name": label.get("name")} for label in raw.get("labels") or []
                   if isinstance(label, dict)],
    }


def list_prs(gh, head, state="open"):
    """[pr_row] for `head`. Raises GhError when the read did not answer."""
    rows = _json(gh, pr_list(head, state), "listing the PRs for %s" % head)
    if not isinstance(rows, list):
        raise GhError("listing the PRs for %s" % head, "gh api returned no list")
    return [pr_row(r) for r in rows if isinstance(r, dict)]


def review_decision(reviews):
    """APPROVED | CHANGES_REQUESTED | REVIEW_REQUIRED from the review list.

    Each reviewer's LATEST deciding review counts, as GitHub's own decision
    does; a dismissed review stands for nothing. One standing request for
    changes outweighs any approval."""
    latest = {}
    for review in reviews or []:
        if not isinstance(review, dict):
            continue
        state = str(review.get("state") or "").upper()
        login = ((review.get("user") or {}).get("login") or "").lower()
        if state in _DECIDING_REVIEWS and login:
            latest[login] = state
    standing = set(latest.values())
    if "CHANGES_REQUESTED" in standing:
        return "CHANGES_REQUESTED"
    if "APPROVED" in standing:
        return "APPROVED"
    return "REVIEW_REQUIRED"


def required_contexts(gh, base):
    """The status-check names `base`'s protection requires ([] when none)."""
    branch = _json(gh, api("%s/branches/%s" % (REPO, quote(base, safe=""))),
                   "reading %s's branch protection" % base)
    checks = ((branch.get("protection") or {}).get("required_status_checks") or {}) \
        if isinstance(branch, dict) else {}
    return [c for c in checks.get("contexts") or [] if isinstance(c, str)]


def status_rollup(gh, sha, required):
    """Check runs plus commit statuses for `sha`, in statusCheckRollup's shape."""
    required = set(required or ())
    rollup = []
    runs = _json_lines(gh, api("%s/commits/%s/check-runs?per_page=100" % (REPO, sha),
                               "--paginate", "--jq", ".check_runs[]"),
                       "reading the check runs on %s" % sha)
    for check in runs:
        if not isinstance(check, dict):
            continue
        rollup.append({"name": check.get("name"),
                       "status": str(check.get("status") or "").upper(),
                       "conclusion": str(check.get("conclusion") or "").upper(),
                       "isRequired": check.get("name") in required})
    combined = _json(gh, api("%s/commits/%s/status" % (REPO, sha)),
                     "reading the commit statuses on %s" % sha)
    for status in (combined or {}).get("statuses") or []:
        if not isinstance(status, dict):
            continue
        rollup.append({"context": status.get("context"),
                       "state": str(status.get("state") or "").upper(),
                       "isRequired": status.get("context") in required})
    return rollup


def view_pr(gh, number, full=True):
    """The `gh pr view --json` document readiness and exempt-PR mode read.

    Carries every key of readiness.PR_VIEW_FIELDS plus `labels`, and the
    `requiredContexts` the base's protection names, so `required_checks` can
    answer from the same reads. `full=False` stops after the pull itself (its
    state, branches, draft flag and labels). Raises GhError when any read did not answer:
    a partial document must never look like a complete one."""
    raw = _json(gh, api("%s/pulls/%s" % (REPO, number)), "reading PR %s" % number)
    if not isinstance(raw, dict) or "number" not in raw:
        raise GhError("reading PR %s" % number, "gh api returned no pull request")
    doc = pr_row(raw)
    if not full:
        return doc
    doc["mergeable"] = _MERGEABLE.get(raw.get("mergeable"), "UNKNOWN")
    doc["mergeStateStatus"] = str(raw.get("mergeable_state") or "unknown").upper()
    reviews = _json_lines(gh, api("%s/pulls/%s/reviews?per_page=100" % (REPO, number),
                                  "--paginate", "--jq", ".[]"),
                          "reading PR %s's reviews" % number)
    doc["reviewDecision"] = review_decision(reviews)
    required = required_contexts(gh, doc["baseRefName"] or "")
    doc["requiredContexts"] = required
    doc["statusCheckRollup"] = status_rollup(gh, (raw.get("head") or {}).get("sha"),
                                             required)
    return doc


#: Matches readiness.NO_REQUIRED_CHECKS_MARKERS: a base with no required checks.
NO_REQUIRED = "no required checks reported on the %s branch"


def required_checks(doc):
    """True, or (False, detail), for a view_pr document's required checks.

    The second, independent CI signal readiness consults: every context the
    base's protection requires must have REPORTED and passed. The rollup's
    `isRequired` flags cover a check that ran; this covers one that never did,
    which the rollup alone cannot show."""
    required = doc.get("requiredContexts") or []
    if not required:
        return (False, NO_REQUIRED % (doc.get("baseRefName") or "base"))
    seen = {}
    for entry in doc.get("statusCheckRollup") or []:
        name = entry.get("name") or entry.get("context")
        if name in required:
            seen.setdefault(name, []).append(entry)
    missing = [name for name in required if name not in seen]
    if missing:
        return (False, "required check(s) not reported: %s" % ", ".join(missing))
    from .readiness import check_state
    red = sorted(name for name, entries in seen.items()
                 if any(check_state(e) != "pass" for e in entries))
    if red:
        return (False, "required check(s) not green: %s" % ", ".join(red))
    return True


def find_milestone(gh, title):
    """The number of the milestone titled `title`, or None."""
    for row in _json_lines(gh, milestones(), "listing milestones"):
        if isinstance(row, dict) and row.get("title") == title:
            return row.get("number")
    return None


__all__ = ["REPO", "NOT_ON_PATH", "GhError", "run", "api", "label_create", "issue_create",
           "issue_edit_body", "issue_set_milestone", "add_labels", "add_assignees",
           "request_reviewers", "pr_create", "user_login", "issue_view", "pr_url",
           "pr_files", "milestones", "pr_list", "pr_state", "pr_row", "list_prs",
           "review_decision", "required_contexts", "status_rollup", "view_pr",
           "NO_REQUIRED", "required_checks", "find_milestone"]
