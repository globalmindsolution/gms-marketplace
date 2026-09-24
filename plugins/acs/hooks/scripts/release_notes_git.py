"""release_notes_git — the git and forge reads a release needs
(extracted from release_notes.py by MAR-531).

Every shell-out lives here: tag lookup and creation time, the release branch,
and `gh pr list`. Isolating them is what lets the enumeration
(`release_notes_tickets`) and the rendering be exercised from recorded output
instead of a live repo.
"""


import datetime
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from release_notes_config import ReleaseNotesError


VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ---------------------------------------------------------------------------
# Version / datetime helpers
# ---------------------------------------------------------------------------

def _is_valid_version(version):
    return bool(VERSION_RE.match(version or ""))


def _parse_iso(value):
    """Parse an ISO-8601 datetime (accepts a trailing 'Z'); returns None on any failure."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# git / gh helpers — argument lists only, never a shell string
# ---------------------------------------------------------------------------

def _run_git(repo_root, args):
    return subprocess.run(["git"] + args, cwd=repo_root, capture_output=True, text=True)


def since_tag(repo_root, base_branch):
    """git describe --tags --abbrev=0 <base_branch> -> tag string, or None (bootstrap case)."""
    result = _run_git(repo_root, ["describe", "--tags", "--abbrev=0", base_branch])
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


def tag_creation_time(repo_root, tag):
    result = _run_git(
        repo_root, ["for-each-ref", "--format=%(creatordate:iso-strict)", "refs/tags/%s" % tag],
    )
    if result.returncode != 0:
        return None
    out = result.stdout.strip()
    return out or None


def tag_exists(repo_root, rendered_tag):
    result = _run_git(repo_root, ["rev-parse", "-q", "--verify", "refs/tags/%s" % rendered_tag])
    return result.returncode == 0


def release_branch(repo_root, rendered_branch):
    result = _run_git(repo_root, ["ls-remote", "--heads", "origin", "refs/heads/%s" % rendered_branch])
    if result.returncode == 0 and result.stdout.strip():
        return rendered_branch
    return None


def gh_pr_list(repo_root, rendered_branch):
    """The single `gh` seam: resolve the open PR for `rendered_branch`, or None. Tests monkeypatch this.

    None means ASKED, AND THERE IS NO OPEN PR. A failure to ask at all -- gh
    absent from PATH, expired auth, a 403 on a managed session, a rate limit,
    output that is not JSON -- raises `ReleaseNotesError` instead, so `status`
    exits 2 with gh's own words rather than printing `"open_pr": null`.

    Collapsing the two was a fail-open idempotency gate. `open_pr` is the
    whole of /acs:release's re-run safety (release/SKILL.md Step 2): read as
    "no cut in flight", an unevaluable probe is exactly the state in which a
    second release PR gets opened for a version that already has one. ADR-0088
    classifies a gate-input read that could not be evaluated as CRITICAL for
    that reason -- an unevaluable gate is never treated as passed -- and
    `gh pr list` is named there among them.
    """
    argv = ["gh", "pr", "list", "--head", rendered_branch, "--state", "open",
            "--json", "number,url"]
    try:
        result = subprocess.run(argv, cwd=repo_root, capture_output=True, text=True)
    except OSError as exc:
        raise ReleaseNotesError(
            "cannot resolve whether a release PR is already open for %s: "
            "`gh pr list` could not be run (%s). gh (the GitHub CLI) is acs's "
            "only GitHub transport (ADR-0088); install and authenticate it "
            "(gh auth login), or confirm by hand that no PR is open for that "
            "branch before cutting." % (rendered_branch, exc))
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ReleaseNotesError(
            "cannot resolve whether a release PR is already open for %s: "
            "`gh pr list` exited %d%s"
            % (rendered_branch, result.returncode, ": " + detail if detail else ""))
    try:
        data = json.loads(result.stdout)
    except ValueError:
        raise ReleaseNotesError(
            "cannot resolve whether a release PR is already open for %s: "
            "`gh pr list` returned output that is not JSON" % rendered_branch)
    if isinstance(data, list) and data:
        entry = data[0]
        if isinstance(entry, dict) and "number" in entry:
            return {"number": entry["number"], "url": entry.get("url")}
    return None
