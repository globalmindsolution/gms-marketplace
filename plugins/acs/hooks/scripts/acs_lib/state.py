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
from .repo import _guarded_repo_write, checkout_id, checkout_root, index_path, lock_path, repo_dir, scan_local_ticket_evidence, state_path
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
    unless seed_next authoritatively confirms/repairs the floor."""
    rdir = repo_dir(workspace, repo_id)
    os.makedirs(rdir, exist_ok=True)
    guard = os.path.join(rdir, "counters.json.lock")
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
                    os.unlink(guard)  # stale guard from a crashed allocation
                    continue
            except OSError:
                pass
            import time
            time.sleep(0.05)
    try:
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
    finally:
        if acquired:
            try:
                os.unlink(guard)
            except OSError:
                pass


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


def lock_is_stale(lock):
    """A lock is stale when its process is gone (same host) or it is very old."""
    created = parse_iso(lock.get("created_at"))
    age_h = None
    if created:
        age_h = (datetime.now(timezone.utc) - created).total_seconds() / 3600.0
    if lock.get("hostname") == socket.gethostname() and isinstance(lock.get("pid"), int):
        try:
            os.kill(lock["pid"], 0)
            return False
        except ProcessLookupError:
            return True
        except (PermissionError, OSError):
            return False
    return age_h is not None and age_h > 24


def check_lock(tdir, ckid):
    """Returns (ok, message). ok=False means another session holds the lock."""
    lock = read_lock(tdir)
    if not isinstance(lock, dict):
        return True, None
    if lock.get("checkout_id") == ckid:
        return True, None  # re-entrant for the same checkout
    holder = lock.get("checkout_path") or lock.get("checkout_id") or "another session"
    if lock_is_stale(lock):
        return False, (
            "ticket is locked by %s but the lock looks stale (no live process / very old). "
            "If you are sure no other session is working this ticket, remove %s manually and retry."
            % (holder, lock_path(tdir))
        )
    return False, "ticket is locked by another session (%s, since %s)." % (holder, lock.get("created_at"))


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
    lock = read_lock(tdir)
    if lock and cwd is not None and lock.get("checkout_id") != checkout_id(cwd):
        return False  # never release someone else's lock
    try:
        os.unlink(lock_path(tdir))
        return True
    except OSError:
        return False
