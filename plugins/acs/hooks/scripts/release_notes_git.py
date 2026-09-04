"""release_notes_git — the git and forge reads a release needs
(extracted from release_notes.py by MAR-531).

Every shell-out lives here: tag lookup and creation time, the release branch,
and `gh pr list`. Isolating them is what lets the enumeration and rendering
above be exercised from recorded output instead of a live repo.
"""


import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile


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
    """The single `gh` seam: resolve the open PR for `rendered_branch`, or None. Tests monkeypatch this."""
    result = subprocess.run(
        ["gh", "pr", "list", "--head", rendered_branch, "--state", "open", "--json", "number,url"],
        cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except ValueError:
        return None
    if isinstance(data, list) and data:
        entry = data[0]
        if isinstance(entry, dict) and "number" in entry:
            return {"number": entry["number"], "url": entry.get("url")}
    return None
