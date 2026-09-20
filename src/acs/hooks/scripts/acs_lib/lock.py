"""acs_lib.lock — the run lock and its audit ledger.

Extracted from `acs_lib.state`, which owned six unrelated things because they
all happened to live in the same directory (§4.1). The PROTOCOL is unchanged
and deliberately so: re-entrant for the same checkout, fail-closed for any
other, stale only on evidence rather than on a guess, and a forced release
always audited to an append-only ledger. It was expensive to get right and
the redesign keeps it verbatim.

What moved is only WHERE it lives: from the ticket partition to the run
partition (`runs/<run-id>/lock.json`). Two runs on the same subject are two
partitions and two locks; `acs run new` refuses the second unless the first is
terminal.
"""

import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from ._common import GateError, now_iso, parse_iso, read_json, write_json
from .repo import checkout_id, lock_path

def read_lock(tdir):
    return read_json(lock_path(tdir))


#: How long a lock with NO liveness signal is honoured before it reads as
#: abandoned. A timeout, not a probe -- see lock_staleness.
LOCK_MAX_AGE_HOURS = 24

#: What each lock_staleness basis means, in one clause, for the operator-facing
#: messages check_lock builds.
LOCK_STALENESS_REASONS = {
    "holder-process-gone": "the holding process on this host is gone",
    "holder-process-live": "the holding process on this host is alive",
    "holder-process-unprobeable": "the holding pid exists on this host but is not ours to probe",
    "age-timeout": "no liveness signal is available and it is older than %dh" % LOCK_MAX_AGE_HOURS,
    "age-within-timeout": "no liveness signal is available and it is younger than %dh" % LOCK_MAX_AGE_HOURS,
    "age-unknown": "no liveness signal is available and it carries no readable created_at",
}


def lock_staleness(lock):
    """(stale, basis) for a ticket lock -- the reasoning behind lock_is_stale.

    There are two regimes, and only ONE of them observes the holder at all:

    * SAME HOST -- `hostname` equals this machine's and `pid` is an int:
      os.kill(pid, 0) is a real liveness probe. A live pid is never stale;
      ProcessLookupError means the holder is gone. A PermissionError means a
      process with that pid exists but belongs to another user, which is not
      evidence the holder died, so it counts as live.

    * EVERY OTHER CASE -- a different hostname, an absent hostname, or a
      non-integer pid: **there is no liveness signal whatsoever**. The recorded
      pid belongs to another machine's (or another container's) pid namespace;
      probing it here would answer a question about an unrelated local process,
      so this function deliberately does not. Age is all that is left, and the
      verdict degrades to a LOCK_MAX_AGE_HOURS (24h) timeout: a holder that is
      alive and working
      on another host reads as "not stale" only until the timeout elapses,
      after which a LIVE holder reads as stale. Containers, CI runners and
      worktrees on different machines share the workspace but not the pid
      namespace, so this is the ordinary case, not the exotic one.

    The timeout removes nothing by itself. check_lock reports the verdict and
    its basis and leaves the decision to the operator, who breaks the lock
    through force_release_lock -- which records who broke it and why.
    """
    if lock.get("hostname") == socket.gethostname() and isinstance(lock.get("pid"), int):
        try:
            os.kill(lock["pid"], 0)
            return False, "holder-process-live"
        except ProcessLookupError:
            return True, "holder-process-gone"
        except (PermissionError, OSError):
            return False, "holder-process-unprobeable"
    created = parse_iso(lock.get("created_at"))
    if created is None:
        return False, "age-unknown"
    age_h = (datetime.now(timezone.utc) - created).total_seconds() / 3600.0
    if age_h > LOCK_MAX_AGE_HOURS:
        return True, "age-timeout"
    return False, "age-within-timeout"


def lock_is_stale(lock):
    """A lock is stale when its process is gone (same host) or, with no liveness
    signal at all, when it has outlived LOCK_MAX_AGE_HOURS. lock_staleness
    documents which of those two regimes applies and what each cannot see."""
    return lock_staleness(lock)[0]


def check_lock(tdir, ckid):
    """Returns (ok, message). ok=False means another session holds the lock.

    The message names the staleness BASIS (lock_staleness), so an operator can
    tell "the holder is provably gone" from "we cannot see the holder at all
    and the clock ran out" -- two very different reasons to break a lock."""
    lock = read_lock(tdir)
    if not isinstance(lock, dict):
        return True, None
    if lock.get("checkout_id") == ckid:
        return True, None  # re-entrant for the same checkout
    holder = lock.get("checkout_path") or lock.get("checkout_id") or "another session"
    stale, basis = lock_staleness(lock)
    if stale:
        return False, (
            "ticket is locked by %s but the lock looks stale (%s). "
            "If you are sure no other session is working this ticket, break it with "
            "`acs.py lock force-unlock --reason \"...\"` (which records who broke it), "
            "or remove %s manually, and retry."
            % (holder, LOCK_STALENESS_REASONS[basis], lock_path(tdir))
        )
    return False, ("ticket is locked by another session (%s, since %s; %s)."
                   % (holder, lock.get("created_at"), LOCK_STALENESS_REASONS[basis]))


def acquire_lock(tdir, cwd):
    ckid = checkout_id(cwd)
    ok, msg = check_lock(tdir, ckid)
    if not ok:
        raise GateError(msg)
    write_json(lock_path(tdir), {
        "checkout_id": ckid,
        "checkout_path": checkout_root(cwd) or os.path.abspath(cwd),
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "created_at": now_iso(),
    })


def release_lock(tdir, cwd=None):
    """Release the lock this checkout holds. Refuses another checkout's lock --
    breaking one of those is force_release_lock's job, and is audited."""
    lock = read_lock(tdir)
    if lock and cwd is not None and lock.get("checkout_id") != checkout_id(cwd):
        return False  # never release someone else's lock
    try:
        os.unlink(lock_path(tdir))
        return True
    except OSError:
        return False


#: The ticket-scoped, append-only ledger of lock breaks. JSONL, one object per
#: line, the same shape cost_sampler uses for its sample log.
LOCK_AUDIT_FILENAME = "lock-events.jsonl"


def lock_audit_path(tdir):
    return os.path.join(tdir, LOCK_AUDIT_FILENAME)


def append_lock_event(tdir, event):
    """Append one JSON object to the ticket's lock ledger and return its path."""
    path = lock_audit_path(tdir)
    os.makedirs(tdir, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")
    return path


def force_release_lock(tdir, cwd, reason, actor=None):
    """Break a ticket lock this checkout does NOT hold, recording who and why.

    release_lock refuses another checkout's lock by design. That is the right
    default and it left no way out: a container that died mid-run holds a lock
    whose pid this host cannot probe (see lock_staleness), so the lock is not
    even reported as stale until the LOCK_MAX_AGE_HOURS (24h) timeout elapses,
    and the only
    remedy was "delete the file", which leaves no trace of who decided that.

    This is the explicit path, and it is deliberately not automatic:

      * it REQUIRES a non-empty reason;
      * it does not consult lock_staleness for permission -- breaking a lock is
        an operator's call, and the audit entry is what makes the call
        reviewable -- but it does RECORD the verdict and its basis, so the
        ledger shows what was known at the time;
      * it appends the audit entry BEFORE unlinking. A crash between the two
        leaves a recorded break with the lock still in place (visible, and
        harmless to repeat); the other order would leave a broken lock nobody
        can trace. A failed unlink appends a second entry saying so.

    Returns a dict; raises GateError only when the audit entry was written and
    the unlink then failed.
    """
    if not (reason or "").strip():
        raise ValueError("force_release_lock requires a non-empty reason")
    lock = read_lock(tdir)
    if not isinstance(lock, dict):
        return {"forced": False, "detail": "no lock file at %s" % lock_path(tdir),
                "lock": None, "audit_path": None}
    stale, basis = lock_staleness(lock)
    event = {
        "event": "lock_force_released",
        "at": now_iso(),
        "reason": reason.strip(),
        "actor": actor,
        "by_checkout_id": checkout_id(cwd) if cwd else None,
        "by_checkout_path": (checkout_root(cwd) or os.path.abspath(cwd)) if cwd else None,
        "by_pid": os.getpid(),
        "by_hostname": socket.gethostname(),
        "broken_lock": lock,
        "staleness_verdict": stale,
        "staleness_basis": basis,
    }
    audit = append_lock_event(tdir, event)
    try:
        os.unlink(lock_path(tdir))
    except OSError as exc:
        append_lock_event(tdir, {"event": "lock_force_release_failed", "at": now_iso(),
                                 "error": str(exc), "reason": event["reason"]})
        raise GateError("recorded the break in %s but could not remove %s: %s"
                        % (audit, lock_path(tdir), exc))
    return {"forced": True, "detail": "lock broken", "lock": lock,
            "audit_path": audit, "event": event}
