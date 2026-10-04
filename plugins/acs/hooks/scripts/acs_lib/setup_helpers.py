"""acs_lib.setup_helpers — extracted from acs_lib.py by MAR-522."""


import fnmatch
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
import claude_code_adapter as cc  # noqa: E402

from ._common import TICKET_ID_RE
from . import conventions
from .repo import ticket_id_from_text



# ---------------------------------------------------------------------------
# Exempt non-ticket /acs:merge-pr argument classifier (MAR-9, clarification C-3).
# Pure: given the raw arg string it decides ticket-backed vs exempt-pr and parses
# the PR ref for the exempt case. The caller supplies ticket_resolves (whether a
# pointer/branch already yields a ticket) to disambiguate a bare integer.
# ---------------------------------------------------------------------------

_PR_URL_RE = re.compile(r"/pull/(\d+)\b")
_PR_FLAG_RE = re.compile(r"--pr[=\s]+(\d+)\b")
_PR_HASH_RE = re.compile(r"#(\d+)\b")
_BARE_INT_RE = re.compile(r"^\s*(\d+)\s*$")


def classify_merge_pr_arg(args_text, ticket_prefix=None, ticket_resolves=False):
    """Classify a /acs:merge-pr argument string.

    Returns (kind, pr_ref):
      ("exempt-pr", "<n>") for the non-ticket merge forms — an explicit
        --pr <n> flag, a #<n> token, a PR URL (.../pull/<n>), or a bare integer
        that is NOT a ticket id AND no ticket already resolves from pointer/branch.
      ("ticket", None) for a ticket-id-shaped token (the ticket gate always wins),
        a bare integer when a ticket resolves (prefer ticket when ambiguous), and
        any empty/unrecognized input (let the existing ticket gate produce its
        existing error). Per clarification C-3."""
    text = args_text or ""
    # A ticket-id-shaped token always wins — preserves AC-8.
    if ticket_id_from_text(text, ticket_prefix):
        return ("ticket", None)
    # Explicit forms are ALWAYS exempt (C-3), regardless of ticket_resolves.
    m = _PR_FLAG_RE.search(text)
    if m:
        return ("exempt-pr", m.group(1))
    m = _PR_URL_RE.search(text)
    if m:
        return ("exempt-pr", m.group(1))
    m = _PR_HASH_RE.search(text)
    if m:
        return ("exempt-pr", m.group(1))
    # A bare integer is exempt only when no ticket resolves (C-3: prefer ticket).
    m = _BARE_INT_RE.match(text)
    if m and not ticket_resolves:
        return ("exempt-pr", m.group(1))
    return ("ticket", None)


def _pr_labels(pr):
    """gh pr view --json labels yields [{"name": ...}, ...]; normalize to names."""
    out = []
    for label in pr.get("labels") or []:
        if isinstance(label, dict) and label.get("name"):
            out.append(label["name"])
        elif isinstance(label, str):
            out.append(label)
    return out


def validate_exempt_pr(pr, settings):
    """Validate a PR (the parsed `gh pr view` JSON object) for the exempt-pr merge
    path. Returns (ok, message): ok True means the PR is a sanctioned exempt PR;
    ok False means refuse, and `message` is the user-facing reason (already
    carrying the /acs:merge-pr <ticket> redirect when the PR looks ticket-backed).
    Mirrors templates/ci/check-conventions.py is_exempt (label first, then branch
    glob) and the C-3 ticket-backed refusal."""
    branch = pr.get("headRefName") or ""
    labels = _pr_labels(pr)
    exempt_label = conventions.EXEMPT_LABEL
    require_label = conventions.PIPELINE_LABEL
    exempt_branches = conventions.EXEMPT_BRANCHES
    prefix = (settings or {}).get("ticket_prefix")

    # OPEN + not draft.
    state = (pr.get("state") or "").upper()
    if state != "OPEN":
        return (False, "PR #%s is %s, not OPEN — only an open PR can be merged."
                % (pr.get("number"), state or "in an unknown state"))
    if pr.get("isDraft"):
        return (False, "PR #%s is a draft — mark it ready for review before merging."
                % pr.get("number"))

    # Ticket-backed → refuse + redirect (C-3). Checked before the exempt grant so
    # a PR that is BOTH ticket-labelled and exempt-labelled still routes to the
    # ticket path.
    embedded = ticket_id_from_text(branch, prefix)
    if require_label in labels or embedded:
        target = embedded or "<TICKET-ID>"
        return (False,
                "PR #%s looks ticket-backed (%s) — merge it through the ticket "
                "path: /acs:merge-pr %s, not the exempt --pr path."
                % (pr.get("number"),
                   "carries the '%s' label" % require_label if require_label in labels
                   else "branch '%s' embeds %s" % (branch, embedded),
                   target))

    # Exempt grant: label first, then branch glob.
    if exempt_label and exempt_label in labels:
        return (True, "label '%s' present" % exempt_label)
    for pattern in exempt_branches:
        if branch and fnmatch.fnmatch(branch, pattern):
            return (True, "branch matches exempt pattern '%s'" % pattern)

    return (False,
            "PR #%s is not a sanctioned exempt PR — label it '%s' (or use an "
            "exempt branch) for the --pr path, or merge it through a ticket: "
            "/acs:merge-pr <TICKET-ID>." % (pr.get("number"), exempt_label))


def tracker_cli_warning(settings):
    provider = (settings.get("tracker") or {}).get("provider", "local")
    if provider == "github" and not shutil.which("gh"):
        return "tracker.provider is 'github' but the gh CLI is not installed — tracker sync will fail."
    return None


# Every external tool the full acs workflow touches. kind: required (no pipeline
# without it), recommended (a major capability needs it), optional (graceful
# fallback). gh is bumped to required by tracker provider. /setup's Step 0b
# preflight reports these and offers to install the missing ones.
TOOLCHAIN = [
    {"name": "git", "kind": "required",
     "why": "version control — every skill operates on the repo and its branches",
     "install": {"macos": "xcode-select --install", "debian": "apt-get install -y git"}},
    {"name": "python3", "kind": "required",
     "why": "runs the hooks, gates, convention checker, and helper CLIs (stdlib only)",
     "install": {"macos": "brew install python", "debian": "apt-get install -y python3"}},
    {"name": "gh", "kind": "recommended",
     "why": "create-pr / merge-pr, labels, branch protection; required for github tracker sync",
     "install": {"macos": "brew install gh",
                 "debian": "see https://github.com/cli/cli/blob/trunk/docs/install_linux.md"}},
    {"name": "pre-commit", "kind": "recommended",
     "why": "shared, tracked local checks (a repo's own pre-commit configuration)",
     "install": {"macos": "brew install pre-commit",
                 "any": "pipx install pre-commit   # or: pip install --user pre-commit"}},
]


def _tool_version(name):
    """Best-effort one-line version string for an installed tool, or None."""
    try:
        out = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=5)
        lines = (out.stdout or out.stderr or "").splitlines()
        return lines[0].strip() if lines else None
    except (OSError, subprocess.SubprocessError):
        return None


def check_toolchain(settings=None):
    """Status of every tool the full acs workflow uses (for /setup's preflight).

    Returns a list of dicts: name, kind (required|recommended|optional), present
    (bool), version (str|None), why, install (platform -> command). A tool's kind
    is bumped to 'required' when settings make it mandatory (tracker provider).
    """
    provider = ((settings or {}).get("tracker") or {}).get("provider", "local")
    rows = []
    for spec in TOOLCHAIN:
        kind = spec["kind"]
        if spec["name"] == "gh" and provider == "github":
            kind = "required"
        present = shutil.which(spec["name"]) is not None
        rows.append({
            "name": spec["name"], "kind": kind, "present": present,
            "version": _tool_version(spec["name"]) if present else None,
            "why": spec["why"], "install": spec["install"],
        })
    return rows


def missing_tools(settings=None, kinds=("required", "recommended"), rows=None):
    """Names of not-present tools in the given kinds — what /setup should offer to install.

    `rows` reuses an already-probed check_toolchain() result. Without it, a
    caller wanting both the table and the missing list either probes every tool
    twice — each probe a subprocess with a 5s timeout — or re-implements this
    predicate, and the two answers to "which tools are missing?" drift apart."""
    return [r["name"] for r in (check_toolchain(settings) if rows is None else rows)
            if r["kind"] in kinds and not r["present"]]
