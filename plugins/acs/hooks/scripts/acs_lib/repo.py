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
import time
from contextlib import contextmanager
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


#: The repo-level write guard's bounded spin, unchanged from the pattern this
#: replaces: 200 attempts 0.05s apart, a 10-second budget.
GUARD_ATTEMPTS = 200
GUARD_INTERVAL = 0.05
#: Overrides GUARD_ATTEMPTS. Now that exhaustion REFUSES the write rather than
#: performing it unguarded, the budget is the difference between waiting out a
#: slow writer and failing a phase, so it is operable: raise it for a workspace
#: on slow shared storage, and drop it to make a test's refusal arm immediate.
GUARD_ATTEMPTS_ENV = "ACS_GUARD_ATTEMPTS"
#: The FLOOR for treating a guard file as abandoned by a crashed writer. The
#: effective threshold is guard_stale_seconds(), which never lets a reclaim
#: happen before the waiter's own budget would have expired -- see there.
GUARD_STALE_SECONDS = 30


class GuardTimeout(GateError):
    """A repo-level write guard was held by another writer for the whole budget.

    MAR-530: until this ticket, exhausting the spin was SILENT. `acquired`
    stayed False and the read-modify-write ran anyway, so the guard covered
    every case except the one it exists for -- a concurrent writer holding it
    -- and the update it was meant to protect could be clobbered with nothing
    recording that it happened. Exhaustion now raises: the caller reports a
    refused write, which is recoverable, instead of performing an unguarded one
    whose loss is invisible.

    A GateError subclass, so the pre-hook's existing handler reports it as a
    blocked skill (exit 2) rather than a traceback.
    """


#: Ceiling on $ACS_GUARD_ATTEMPTS. The pre-hook is bounded at 25s by Claude
#: Code, so a budget past that cannot be waited out there anyway; past this an
#: operator has configured a hang, not a wait.
GUARD_ATTEMPTS_MAX = 6000


def guard_attempts():
    """GUARD_ATTEMPTS, or a positive integer from $ACS_GUARD_ATTEMPTS.

    Read per call, not at import: a hook process is short-lived, and a test or
    an operator setting the variable should not depend on import order. A
    missing, non-numeric or non-positive value falls back to the default rather
    than producing a zero-attempt guard that refuses everything, and a value
    past GUARD_ATTEMPTS_MAX is clamped: only the lower bound used to be
    checked, so `ACS_GUARD_ATTEMPTS=20000` bought a 17-minute spin inside a
    hook Claude Code kills at 25 seconds."""
    try:
        override = int(os.environ.get(GUARD_ATTEMPTS_ENV, ""))
    except ValueError:
        return GUARD_ATTEMPTS
    if override <= 0:
        return GUARD_ATTEMPTS
    return min(override, GUARD_ATTEMPTS_MAX)


def guard_stale_seconds(attempts, interval):
    """How old a guard file must be before a waiter may reclaim it.

    MAR-530 made the budget operable (`$ACS_GUARD_ATTEMPTS`) but left this
    threshold fixed at 30s -- so raising the budget for slow shared storage
    made things WORSE, not better: with a 100-second budget every waiter
    outlived the threshold and stole the guard from a live holder, putting two
    writers inside the body at once and restoring exactly the lost update this
    ticket exists to close. The threshold now moves with the budget, and by
    twice it, so a reclaim can never happen while any writer configured the
    same way could still legitimately be holding on."""
    return max(GUARD_STALE_SECONDS, 2 * attempts * interval)


def _guard_owner(pid=None):
    """The identity written into a guard file, so its holder is knowable."""
    return {"pid": os.getpid() if pid is None else pid,
            "host": socket.gethostname(), "at": now_iso()}


def _read_guard_owner(guard):
    doc = read_json(guard)
    return doc if isinstance(doc, dict) else None


def _guard_holder_is_alive(owner):
    """True when the guard's recorded holder is a process still running HERE.

    An age threshold alone cannot tell a crashed writer from a slow one, so a
    long-but-live hold was reclaimed as if it had crashed. On this host that is
    answerable exactly: signal 0 probes the pid without touching it. A holder
    on another host is unknowable, so it falls back to the age threshold --
    which is why that threshold now derives from the budget."""
    if not owner or owner.get("host") != socket.gethostname():
        return False
    try:
        pid = int(owner.get("pid"))
    except (TypeError, ValueError):
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # EPERM: a process we may not signal is still a process
    return True


@contextmanager
def repo_guard(rdir, guard_name, attempts=None, interval=GUARD_INTERVAL):
    """Hold `<rdir>/<guard_name>` as an O_EXCL guard for the body (D5.1(a)).

    The spin is bounded (`attempts`, defaulting to guard_attempts(), x
    `interval`), and a guard file older than
    GUARD_STALE_SECONDS is treated as abandoned by a crashed writer and removed.
    If the guard is still held when the budget runs out this raises
    GuardTimeout WITHOUT running the body and WITHOUT touching the foreign
    guard file -- refusing the write is the whole point (see GuardTimeout).

    The guard is a file, not an OS lock: it protects concurrent acs writers on
    one filesystem, not against a writer that ignores it.
    """
    attempts = guard_attempts() if attempts is None else attempts
    stale_after = guard_stale_seconds(attempts, interval)
    os.makedirs(rdir, exist_ok=True)
    guard = os.path.join(rdir, guard_name)
    mine = _guard_owner()
    acquired = False
    for _ in range(attempts):
        try:
            fd = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, json.dumps(mine).encode("utf-8"))
            finally:
                os.close(fd)
            acquired = True
            break
        except FileExistsError:
            try:
                age = datetime.now(timezone.utc).timestamp() - os.path.getmtime(guard)
                if age > stale_after and not _guard_holder_is_alive(_read_guard_owner(guard)):
                    os.unlink(guard)  # abandoned by a writer that crashed
                    continue
            except OSError:
                pass
            time.sleep(interval)
    if not acquired:
        raise GuardTimeout(
            "could not acquire %s within %.1fs -- another writer is holding it. "
            "The write was REFUSED, not performed unguarded: retry once that writer "
            "finishes. A guard left by a crashed writer is reclaimed automatically "
            "after %.0fs, so deleting one by hand is never required."
            % (guard, attempts * interval, stale_after))
    try:
        yield guard
    finally:
        # Unlink only OUR guard. A waiter that reclaimed this file as abandoned
        # now owns a NEW guard at the same path; unlinking blindly would strip
        # the guard off a live writer -- the same double-entry the reclaim rule
        # above exists to prevent, arriving from the other direction.
        try:
            if _read_guard_owner(guard) == mine:
                os.unlink(guard)
        except OSError:
            pass


def _guarded_repo_write(workspace, repo_id, guard_name, fn):
    """D5.1(a): run fn (a repo_id-keyed read-modify-write) while holding the
    repo-level guard `guard_name`. Raises GuardTimeout instead of running fn
    when the guard cannot be acquired within the budget -- MAR-530 replaced the
    fail-open fallback this and allocate_ticket_id both used."""
    with repo_guard(repo_dir(workspace, repo_id), guard_name):
        return fn()
