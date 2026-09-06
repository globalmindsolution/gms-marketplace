"""acs_lib.state — extracted from acs_lib.py by MAR-522."""


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

from ._common import GateError, PRODUCT_SKILLS, RUN_STATUSES, ReconciliationRequired, now_iso, parse_iso, read_json, write_json
from .repo import _guarded_repo_write, checkout_id, checkout_root, index_path, lock_path, repo_dir, repo_guard, scan_local_ticket_evidence, state_path
from .lanes import VERIFY_ITERATION_CAP, derive_lane, verify_depth
from .metrics import _measure_run_usage, compute_ticket_totals



# ---------------------------------------------------------------------------
# State files (append-only runs; last entry = current state)
# ---------------------------------------------------------------------------

def empty_state(skill, ticket_id):
    return {"skill": skill, "ticket_id": ticket_id, "states": {}, "findings": [], "errors": [], "runs": []}


def load_state(tdir, skill, ticket_id=None):
    state = read_json(state_path(tdir, skill))
    if not isinstance(state, dict) or not isinstance(state.get("runs"), list):
        return empty_state(skill, ticket_id or os.path.basename(tdir))
    return state


def last_run(state):
    runs = state.get("runs") or []
    return runs[-1] if runs else None


def last_run_status(tdir, skill):
    state = read_json(state_path(tdir, skill))
    if not isinstance(state, dict):
        return None
    runs = state.get("runs")
    if not isinstance(runs, list) or not runs:
        return None
    entry = runs[-1]
    return entry.get("status") if isinstance(entry, dict) else None


def skill_completed(tdir, skill):
    return last_run_status(tdir, skill) == "completed"


def append_in_progress_run(tdir, skill, ticket_id, session=None):
    """Append a new in_progress run entry. `session` (an accepted session
    marker dict) is optional -- when given, its session_id/transcript_path are
    persisted onto the entry; the default None keeps every existing caller's
    entry shape byte-identical."""
    state = load_state(tdir, skill, ticket_id)
    entry = {
        "started_at": now_iso(),
        "ended_at": None,
        "tokens": {"input": 0, "output": 0},
        "cost_usd": 0.0,
        "status": "in_progress",
        "stop_reason": None,
    }
    if session:
        entry["session_id"] = session.get("session_id")
        entry["transcript_path"] = session.get("transcript_path")
        # Needed at finalize time to locate this checkout's cost-sample/cursor
        # files (cost_sampler.allocate_cost) -- schema-safe under the run
        # entry's own additionalProperties:true.
        entry["checkout_id"] = session.get("checkout_id")
    state["runs"].append(entry)
    write_json(state_path(tdir, skill), state)
    return state


def finalize_run(tdir, skill, ticket_id, result):
    """Finalize runs[-1] (or append, if the coordinator never registered the run).

    tokens/role_usage/cost_usd/cost_basis are MEASURED (see
    _measure_run_usage), never taken from `result`."""
    state = load_state(tdir, skill, ticket_id)
    # No default: this writes the status the next pre-hook gates on, so a
    # result document that never stated one must fail here rather than
    # silently finalize the run as completed.
    status = result.get("status")
    if status not in RUN_STATUSES or status == "in_progress":
        raise ValueError("invalid final run status: %r" % status)
    entry = last_run(state)
    if not entry or entry.get("status") != "in_progress":
        entry = {"started_at": now_iso(), "tokens": {"input": 0, "output": 0}, "cost_usd": 0.0}
        state["runs"].append(entry)
    entry["ended_at"] = now_iso()
    entry["status"] = status
    entry["stop_reason"] = result.get("stop_reason")
    _measure_run_usage(entry, tdir, skill)
    if status == "handed_off":
        entry["handoff_summary"] = result.get("handoff_summary") or result.get("stop_reason") or ""
    if isinstance(result.get("states"), dict):
        state["states"].update(result["states"])
    if isinstance(result.get("findings"), list):
        state["findings"] = result["findings"]
    if isinstance(result.get("errors"), list):
        state["errors"] = result["errors"]
    write_json(state_path(tdir, skill), state)
    return state, entry


def record_escalation_event(tdir, skill, event):
    """Append `event` (13-field escalation shape) to runs[-1].escalations on
    <skill>-state.json, creating the list if absent. Requires an existing
    in-progress run (last_run(state) must not be None) — callers MUST call
    this only after append_in_progress_run; no run entry is synthesized here.
    Callers MUST NOT call this twice for the same trigger firing."""
    state = load_state(tdir, skill)
    entry = last_run(state)
    if entry is None:
        raise ValueError("record_escalation_event requires an existing run entry "
                          "(call append_in_progress_run first)")
    entry.setdefault("escalations", []).append(event)
    write_json(state_path(tdir, skill), state)
    return state


def confirm_deescalation(tdir, ticket, confirmed_size, confirmed_stakes, clarify_ref):
    """The ONLY function in acs_lib capable of writing a size/stakes value
    lower than the ticket's current confirmed value. REQUIRES clarify_ref
    (a non-empty C-<n> string identifying an answered clarify.py ledger
    entry); raises ValueError if clarify_ref is falsy or does not resolve
    to an answered entry (an "assumed" or "open" entry is rejected, same as
    a missing one) — no write in that case. Recomputes lane via derive_lane
    (never hand-sets it — ADR 0030). Persists ticket.json / pipeline-state.json /
    tickets-index.json exactly like the upward path (save_ticket /
    update_pipeline / update_index), then calls record_escalation_event
    with direction="down" and confirmation_ref=clarify_ref. Callable ONLY
    from the /code coordinator's boundary-only de-escalation subsection —
    never from the in-loop trigger-evaluation code path."""
    if not clarify_ref:
        raise ValueError("confirm_deescalation requires a non-empty clarify_ref")
    ledger = read_json(os.path.join(tdir, "clarifications.json"))
    entries = ledger.get("clarifications") if isinstance(ledger, dict) else None
    entry = next((e for e in (entries or []) if isinstance(e, dict) and e.get("id") == clarify_ref), None)
    if entry is None or entry.get("status") != "answered":
        raise ValueError("clarify_ref %r does not resolve to an answered clarify.py "
                          "ledger entry" % (clarify_ref,))

    from_lane, from_size, from_stakes = ticket["lane"], ticket["size"], ticket["stakes"]
    new_lane = derive_lane(confirmed_size, confirmed_stakes, ticket["needs_design"], ticket["type"])

    ticket["size"] = confirmed_size
    ticket["stakes"] = confirmed_stakes
    ticket["lane"] = new_lane
    save_ticket(tdir, ticket)
    workspace = os.path.dirname(os.path.dirname(tdir))
    repo_id = os.path.basename(os.path.dirname(tdir))
    state = load_state(tdir, "code")
    run_status = (last_run(state) or {}).get("status", "in_progress")
    update_pipeline(tdir, ticket["id"], "code", run_status, lane=new_lane)
    update_index(workspace, repo_id, ticket)

    event = {
        "ts": now_iso(),
        "from_lane": from_lane,
        "to_lane": new_lane,
        "from_size": from_size,
        "from_stakes": from_stakes,
        "to_size": confirmed_size,
        "to_stakes": confirmed_stakes,
        "trigger": "user_confirmed_deescalation",
        "source": "user-confirmed de-escalation via clarify.py %s" % clarify_ref,
        "ceiling_before": VERIFY_ITERATION_CAP[verify_depth(from_lane, from_stakes)],
        "ceiling_after": VERIFY_ITERATION_CAP[verify_depth(new_lane, confirmed_stakes)],
        "direction": "down",
        "confirmation_ref": clarify_ref,
    }
    record_escalation_event(tdir, "code", event)
    return ticket


# ---------------------------------------------------------------------------
# Pipeline ledger (pipeline-state.json)
# ---------------------------------------------------------------------------

def load_pipeline(tdir, ticket_id, flow="ticket"):
    data = read_json(os.path.join(tdir, "pipeline-state.json"))
    if not isinstance(data, dict):
        data = {"ticket_id": ticket_id, "flow": flow, "steps": {}, "totals": {}}
    data.setdefault("steps", {})
    data.setdefault("totals", {})
    return data


def update_pipeline(tdir, ticket_id, skill, status, summary=None, flow=None, lane=None,
                    extra=None):
    """Record a pipeline step transition.

    `extra` merges caller-supplied fields into the step dict (e.g. /ship's
    `fix_loops` counter on the `test` step). Keys the step owns -- status,
    started_at, ended_at, summary -- are never overridden from `extra`; a
    None value deletes the key so a counter can be reset rather than frozen."""
    data = load_pipeline(tdir, ticket_id, flow or ("product" if skill in PRODUCT_SKILLS else "ticket"))
    if flow:
        data["flow"] = flow
    step = data["steps"].setdefault(skill, {})
    if status == "in_progress" and not step.get("started_at"):
        step["started_at"] = now_iso()
    if status != "in_progress":
        step["ended_at"] = now_iso()
    step["status"] = status
    if summary is not None:
        step["summary"] = summary
    if extra:
        reserved = {"status", "started_at", "ended_at", "summary"}
        for key, value in extra.items():
            if key in reserved:
                continue
            if value is None:
                step.pop(key, None)
            else:
                step[key] = value
    if lane is not None:
        data["lane"] = lane
    data["totals"] = compute_ticket_totals(tdir)
    write_json(os.path.join(tdir, "pipeline-state.json"), data)
    return data


# ---------------------------------------------------------------------------
# Tickets, index, counters, metrics
# ---------------------------------------------------------------------------

def load_ticket(tdir):
    return read_json(os.path.join(tdir, "ticket.json"))


def save_ticket(tdir, ticket):
    ticket["updated_at"] = now_iso()
    write_json(os.path.join(tdir, "ticket.json"), ticket)


def new_ticket_doc(ticket_id, title, ttype, **kw):
    return {
        "id": ticket_id,
        "title": title,
        "type": ttype,
        "description": kw.get("description", ""),
        "acceptance_criteria": kw.get("acceptance_criteria", []),
        "priority": kw.get("priority", "medium"),
        "parent": kw.get("parent"),
        "children": kw.get("children", []),
        "status": kw.get("status", "open"),
        "external": kw.get("external"),
        "assignee": kw.get("assignee"),
        "story_points": kw.get("story_points"),
        "needs_design": kw.get("needs_design", ttype == "epic"),
        "docs_only": kw.get("docs_only", False),
        "size":   kw.get("size",   "standard"),
        "stakes": kw.get("stakes", "normal"),
        "lane":   derive_lane(
                      kw.get("size",   "standard"),
                      kw.get("stakes", "normal"),
                      kw.get("needs_design", ttype == "epic"),
                      ttype
                  ),
        "due_date": kw.get("due_date"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def allocate_ticket_id(workspace, repo_id, prefix, repo_root=None, seed_next=None):
    """Allocate the next <prefix>-<n> id; counter guarded by an O_EXCL spin lock so
    parallel worktree sessions never collide. A partition with no reconciliation
    marker refuses (raises ReconciliationRequired) instead of minting from 1,
    unless seed_next authoritatively confirms/repairs the floor.

    Raises GuardTimeout (via repo_guard) rather than minting an id from an
    unguarded read of counters.json -- two sessions handed the same id is the
    exact collision the guard exists to prevent (MAR-530)."""
    rdir = repo_dir(workspace, repo_id)
    with repo_guard(rdir, "counters.json.lock"):
        counters_path = os.path.join(rdir, "counters.json")
        counters = read_json(counters_path) or {}

        if seed_next is not None:
            if seed_next < 1:
                raise ValueError(
                    "allocate_ticket_id requires seed_next >= 1 (defense-in-depth "
                    "behind the CLIs' own >= 1 checks); got %r" % (seed_next,)
                )
            previous_next = counters.get("next")
            if isinstance(previous_next, int) and seed_next < previous_next:
                sys.stderr.write(
                    "acs: warning: --seed-next %d lowers counters.json's next "
                    "(was %d)\n" % (seed_next, previous_next)
                )
            counters["reconciled"] = True
            counters["seed_source"] = "explicit-user"
            counters["seeded_at"] = now_iso()
            counters.pop("observed_max", None)
            counters["next"] = seed_next + 1
            write_json(counters_path, counters)
            return "%s-%d" % (prefix, seed_next)

        if "next" in counters or counters.get("reconciled") is True:
            next_n = int(counters.get("next", 1))
            counters["next"] = next_n + 1
            write_json(counters_path, counters)
            return "%s-%d" % (prefix, next_n)

        scan = scan_local_ticket_evidence(repo_root, prefix)
        observed_max = scan["observed_max"]
        proposed_next = observed_max + 1 if observed_max is not None else None
        raise ReconciliationRequired(prefix, repo_id, observed_max, scan["seed_source"], proposed_next)


def update_index(workspace, repo_id, ticket, archived=None):
    path = index_path(workspace, repo_id)

    def _write():
        data = read_json(path) or {"tickets": {}}
        data.setdefault("tickets", {})
        entry = data["tickets"].setdefault(ticket["id"], {})
        entry.update({
            "id": ticket["id"],
            "title": ticket.get("title"),
            "type": ticket.get("type"),
            "status": ticket.get("status"),
            "parent": ticket.get("parent"),
            "children": ticket.get("children", []),
            "needs_design": ticket.get("needs_design"),
            "lane": ticket.get("lane"),
            "external": ticket.get("external"),
            "due_date": ticket.get("due_date"),
            "updated_at": now_iso(),
        })
        if archived is not None:
            entry["archived"] = archived
        write_json(path, data)
        return data

    return _guarded_repo_write(workspace, repo_id, "tickets-index.json.lock", _write)


# ---------------------------------------------------------------------------
# Locking (.lock per ticket partition; re-entrant per checkout)
# ---------------------------------------------------------------------------

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
