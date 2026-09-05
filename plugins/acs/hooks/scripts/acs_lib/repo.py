"""acs_lib.repo — extracted from acs_lib.py by MAR-522."""


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

from ._common import GateError, TICKET_ID_RE, _git, now_iso, read_json, write_json



# ---------------------------------------------------------------------------
# GitHub CLI failure diagnostics (MAR-403 / ADR-0088)
# ---------------------------------------------------------------------------

GH_ACCESS_DENIED_MARKER = "GitHub access is not enabled for this session"

GH_ACCESS_HINT = (
    "This looks like a session-level access restriction — a Claude Code "
    "cloud/managed session must have the Claude GitHub App connected for this "
    "organization by an org admin. A local Claude Code session uses your own "
    "`gh` authentication and should not see this."
)

GH_GENERIC_HINT = "check `gh auth status` and repo access"


def gh_failure_hint(stderr_text):
    """Classify a gh failure's stderr into one canonical, actionable hint."""
    text = stderr_text if isinstance(stderr_text, str) else str(stderr_text or "")
    if GH_ACCESS_DENIED_MARKER in text:
        return GH_ACCESS_HINT
    return GH_GENERIC_HINT


def gh_read_is_unevaluable(stderr_text):
    """Did this gh read FAIL TO HAPPEN, as opposed to reporting bad news?

    ADR-0088's CRITICAL class is about the first: expired auth, a 403 session
    restriction, a rate limit -- the gate could not be evaluated, so it is
    never treated as passed. A red check is the SECOND kind: gh ran, answered,
    and the answer was "failing". Collapsing both into `returncode != 0` is
    what made an auth failure indistinguishable from a broken build.

    Two things are explicitly NOT unevaluable: a `--required` filter that
    selected nothing (a repo with no branch protection is supported), and an
    empty message, which carries no evidence of an access problem."""
    text = (stderr_text or "").lower()
    if not text.strip():
        return False
    if any(marker in text for marker in
           ("no required checks reported on the", "no checks reported on the")):
        return False
    return any(marker in text for marker in GH_UNEVALUABLE_MARKERS)


#: Substrings that mean the READ failed, not that the checks did.
GH_UNEVALUABLE_MARKERS = (
    GH_ACCESS_DENIED_MARKER.lower(), "http 401", "http 403", "http 5",
    "rate limit", "not logged in", "authentication", "could not resolve host",
    "connection refused", "timeout", "gh auth login",
)


def gh_pr_view(number, fields):
    """`gh pr view <number> --json <fields>`, parsed. Raises GateError with a
    clean message when gh is missing, the lookup fails, or the output does not
    parse -- callers surface that verbatim rather than a traceback.

    The one gh-shell-out helper: skill-start.py's --pr mode and `acs.py
    readiness` both need it, and a second copy would be a second place for the
    missing-gh message and the failure classification to drift. Isolating the
    call here is also what lets tests stub it with a fake gh on PATH.
    """
    try:
        proc = subprocess.run(
            ["gh", "pr", "view", str(number), "--json", fields],
            capture_output=True, text=True,
        )
    except FileNotFoundError:
        raise GateError(
            "gh (the GitHub CLI) is required for --pr mode but was not found on PATH; "
            "install and authenticate it (gh auth login) first.")
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "gh pr view failed"
        raise GateError("could not look up PR %s via gh: %s" % (number, detail))
    try:
        return json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        raise GateError("gh pr view returned no parseable JSON for PR %s" % number)


def gh_pr_required_checks_ok(number):
    """`gh pr checks <number> --required` as a tri-state.

    True (all required checks green), None (gh absent -- unknown, not failing),
    or `(False, detail)` carrying gh's own output so the caller can tell an
    unevaluable read from a red check.

    The second, independent CI signal: GitHub's own answer to "are the REQUIRED
    checks green", which does not depend on `isRequired` being populated in the
    rollup. A missing gh yields None (unknown) rather than False, so a machine
    without the CLI does not report a PR as CI-failing.
    """
    try:
        proc = subprocess.run(["gh", "pr", "checks", str(number), "--required"],
                              capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if proc.returncode == 0:
        return True
    # The detail travels with the answer. Discarding stderr made an
    # UNEVALUABLE read (expired auth, a 403 session restriction, a rate limit)
    # indistinguishable from a red check: both became False, and readiness
    # reported "fail: exited non-zero" naming no check and carrying no gh
    # output. ADR-0088 classifies this read as CRITICAL -- an unevaluable gate
    # is never treated as passed, and the caller needs the text to tell the two
    # apart (and to recognise "no required checks reported", which is neither).
    return (False, (proc.stderr or proc.stdout or "").strip())


# ---------------------------------------------------------------------------
# Repo identity & checkout identity
# ---------------------------------------------------------------------------

_EVIDENCE_RANKS = ("committed-files", "git-history", "branch-names")


def _evidence_source_commands(prefix):
    """The three ranked git argv lists (bounds pinned by the design), in rank order."""
    id_grep = r"\b%s-[0-9]+" % re.escape(prefix)
    return {
        "committed-files": ["grep", "-I", "-E", id_grep, "--", "."],
        "git-history": ["log", "--format=%s%n%b", "-400"],
        "branch-names": ["for-each-ref", "--count=400", "--format=%(refname:short)",
                          "refs/heads", "refs/remotes"],
    }


def scan_local_ticket_evidence(repo_root, prefix):
    """Rank-ordered, bounded, network-free scan for the highest <prefix>-<n> id
    that committed files, git history, or branch names reveal; never raises and
    never touches the network — every source shells out only to `git` via _git,
    which supplies the 10s-per-subprocess timeout and the None-on-failure degrade."""
    per_source = {rank: None for rank in _EVIDENCE_RANKS}
    if repo_root:
        pattern = re.compile(r"\b%s-(\d+)\b" % re.escape(prefix))
        commands = _evidence_source_commands(prefix)
        for rank in _EVIDENCE_RANKS:
            output = _git(commands[rank], repo_root)
            if output:
                ids = [int(match) for match in pattern.findall(output)]
                if ids:
                    per_source[rank] = max(ids)

    observed_max = None
    seed_source = None
    for rank in _EVIDENCE_RANKS:
        value = per_source[rank]
        if value is not None and (observed_max is None or value > observed_max):
            observed_max = value
            seed_source = rank

    return {"observed_max": observed_max, "seed_source": seed_source, "per_source": per_source}


def checkout_root(cwd):
    """Root of the current checkout/worktree."""
    return _git(["rev-parse", "--show-toplevel"], cwd)


def main_repo_root(cwd):
    """Root of the *main* repository, even when cwd is inside a linked worktree."""
    common = _git(["rev-parse", "--git-common-dir"], cwd)
    if not common:
        return None
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    common = os.path.normpath(common)
    if os.path.basename(common) == ".git":
        return os.path.dirname(common)
    return common  # bare-ish layouts; best effort


def repo_partition_id(cwd):
    """Stable per-repo identifier: derived from the git remote (owner-name), so every
    worktree of a repo resolves to the same partition; falls back to the main repo
    directory name when there is no remote."""
    remote = _git(["config", "--get", "remote.origin.url"], cwd)
    if remote:
        path = remote
        path = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", path)   # scheme
        path = re.sub(r"^[^/@]+@", "", path)                       # user@
        path = path.replace(":", "/")
        path = re.sub(r"\.git/?$", "", path)
        segments = [s for s in path.split("/") if s]
        if len(segments) >= 2:
            raw = "%s-%s" % (segments[-2], segments[-1])
        elif segments:
            raw = segments[-1]
        else:
            raw = None
        if raw:
            return re.sub(r"[^A-Za-z0-9._-]+", "-", raw)
    root = main_repo_root(cwd) or checkout_root(cwd)
    if root:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(root))
    return None


def checkout_id(cwd):
    """Stable per-checkout/worktree identifier (one pointer file per parallel session)."""
    root = checkout_root(cwd) or os.path.abspath(cwd)
    digest = hashlib.sha1(os.path.abspath(root).encode("utf-8")).hexdigest()[:8]
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(root))
    return "%s-%s" % (base, digest)


def current_branch(cwd):
    return _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)


def default_state_root(cwd):
    """Derive <main-checkout>/.acs/state-machine straight from git plumbing (D1-D3);
    deliberately does not call main_repo_root(), which cannot tell a bare/submodule
    layout apart from a normal one."""
    is_bare = _git(["rev-parse", "--is-bare-repository"], cwd)
    if not is_bare:
        raise GateError(
            "%s is not a git repository (or git is unavailable); acs cannot derive an "
            "in-repo state root here. Set an explicit workspace_path override." % cwd
        )
    if is_bare == "true":
        raise GateError(
            "%s is a bare git repository; acs cannot derive an in-repo state root here. "
            "Set an explicit workspace_path override." % cwd
        )
    common = _git(["rev-parse", "--git-common-dir"], cwd)
    if not common:
        raise GateError(
            "could not resolve %s's git-common-dir; acs cannot derive an in-repo state "
            "root here. Set an explicit workspace_path override." % cwd
        )
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    common = os.path.normpath(common)
    if os.path.basename(common) != ".git":
        superproject = _git(["rev-parse", "--show-superproject-working-tree"], cwd)
        if superproject:
            raise GateError(
                "%s is a git submodule; acs cannot derive an in-repo state root anchored "
                "to a stable main checkout here. Set an explicit workspace_path override." % cwd
            )
        raise GateError(
            "%s has an unusual git layout (git-common-dir is not a .git directory); acs "
            "cannot derive an in-repo state root here. Set an explicit workspace_path override." % cwd
        )
    root = os.path.dirname(common)
    return os.path.join(root, ".acs", "state-machine")


# ---------------------------------------------------------------------------
# Workspace layout
# ---------------------------------------------------------------------------

def repo_dir(workspace, repo_id):
    return os.path.join(workspace, repo_id)


def ticket_dir(workspace, repo_id, ticket_id):
    return os.path.join(workspace, repo_id, ticket_id)


def archive_dir(workspace, repo_id):
    return os.path.join(workspace, repo_id, "archive")


def sessions_dir(workspace, repo_id):
    return os.path.join(workspace, repo_id, "sessions")


def pointer_path(workspace, repo_id, ckid):
    return os.path.join(sessions_dir(workspace, repo_id), "%s.json" % ckid)


def session_marker_path(workspace, repo_id, ckid):
    """Ticket-independent session-correlation marker, sibling of pointer_path."""
    return os.path.join(sessions_dir(workspace, repo_id), "%s-session.json" % ckid)


def record_session_marker(ctx, payload):
    """Persist the PreToolUse(Skill) envelope's session-correlation fields so
    skill-start.py can thread them onto the new run entry without guessing.
    Fields come straight off the envelope; a missing one is written as null,
    never constructed (e.g. never a cwd-derived guess)."""
    marker = {
        "session_id": cc.hook_session_id(payload),
        "transcript_path": cc.hook_transcript_path(payload),
        "cwd": payload.get("cwd"),
        "checkout_id": ctx["checkout_id"],
        "hook_event_name": cc.hook_event_name(payload),
        "skill": cc.hook_tool_input(payload).get("skill"),
        "updated_at": now_iso(),
    }
    write_json(session_marker_path(ctx["workspace"], ctx["repo_id"], ctx["checkout_id"]), marker)
    return marker


def state_path(tdir, skill):
    return os.path.join(tdir, "%s-state.json" % skill)


def lock_path(tdir):
    return os.path.join(tdir, ".lock")


def find_ticket_partition(workspace, repo_id, ticket_id):
    """Active partition first, then archive/."""
    active = ticket_dir(workspace, repo_id, ticket_id)
    if os.path.isdir(active):
        return active, False
    archived = os.path.join(archive_dir(workspace, repo_id), ticket_id)
    if os.path.isdir(archived):
        return archived, True
    return active, False


# ---------------------------------------------------------------------------
# Ticket id resolution (deterministic: argument -> pointer file -> branch name)
# ---------------------------------------------------------------------------

def ticket_id_from_text(text, prefix=None):
    if not text:
        return None
    if prefix:
        match = re.search(r"\b(%s-\d+)\b" % re.escape(prefix), text)
        if match:
            return match.group(1)
        return None
    match = TICKET_ID_RE.search(text)
    return match.group(1) if match else None


def resolve_ticket_id(cwd, settings, workspace, repo_id, explicit=None, args_text=None):
    prefix = settings.get("ticket_prefix")
    if explicit:
        return explicit.strip(), "argument"
    from_args = ticket_id_from_text(args_text, prefix)
    if from_args:
        return from_args, "argument"
    pointer = read_json(pointer_path(workspace, repo_id, checkout_id(cwd)))
    if isinstance(pointer, dict) and pointer.get("ticket_id"):
        return pointer["ticket_id"], "pointer"
    from_branch = ticket_id_from_text(current_branch(cwd), prefix)
    if from_branch:
        return from_branch, "branch"
    return None, None


def index_path(workspace, repo_id):
    return os.path.join(repo_dir(workspace, repo_id), "tickets-index.json")


def _guarded_repo_write(workspace, repo_id, guard_name, fn):
    """D5.1(a): run fn (a repo_id-keyed read-modify-write) under the same
    O_EXCL spin-lock pattern as allocate_ticket_id's counters guard (bounded
    spin, same 200 x 0.05s budget). Mirrors that pre-existing pattern's
    fail-open fallback: if a live foreign guard is never released within the
    budget, the loop gives up (acquired stays False) and still runs fn()
    unguarded, leaving the foreign guard file untouched -- a best-effort lock,
    not an absolute guarantee against a dropped concurrent update."""
    rdir = repo_dir(workspace, repo_id)
    os.makedirs(rdir, exist_ok=True)
    guard = os.path.join(rdir, guard_name)
    acquired = False
    for _ in range(200):
        try:
            fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            acquired = True
            break
        except FileExistsError:
            try:
                if os.path.getmtime(guard) < datetime.now(timezone.utc).timestamp() - 30:
                    os.unlink(guard)  # stale guard from a crashed writer
                    continue
            except OSError:
                pass
            import time
            time.sleep(0.05)
    try:
        return fn()
    finally:
        if acquired:
            try:
                os.unlink(guard)
            except OSError:
                pass
