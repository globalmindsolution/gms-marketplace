"""acs_lib.metrics — extracted from acs_lib.py by MAR-522."""


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

from ._common import HOOKED_SKILLS, now_iso, parse_iso, read_json, write_json
from .repo import _guarded_repo_write, find_ticket_partition, index_path, repo_dir
from .step import state_path



_EMPTY_MEASURED_TOKENS = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}
_TOKEN_TOTAL_FIELDS = ("input", "output", "cache_creation", "cache_read")


def _sum_role_tokens(role_usage):
    """Sum every role_usage bucket's four token fields (including an
    'unattributed' bucket, if present) into one raw-measured totals dict."""
    totals = dict(_EMPTY_MEASURED_TOKENS)
    for item in role_usage:
        if not isinstance(item, dict):
            continue
        for key in totals:
            value = item.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] += value
    return totals


def _measure_run_usage(entry, tdir, skill):
    """Persist MEASURED tokens/role_usage/model_usage onto `entry` -- read from
    its own recorded transcript (usage_reader) rather than trusting a
    coordinator's self-reported result["tokens"] (AC-3). No dollar cost is
    recorded: its only source was the status line, removed by ADR-0103.

    Required short-circuit (Risk R-N): a run entry with no session_id/
    transcript_path (e.g. new-ticket.py's synthetic, immediately-finalized
    create-ticket runs) never performs transcript I/O -- tokens empty.

    `skill` (the run's own skill, as finalize_run received it) is threaded
    through to usage_reader so it can filter main-session attribution to
    this run's own skill only, excluding same-window records attributed to
    a different acs skill."""
    session_id = entry.get("session_id")
    transcript_path = entry.get("transcript_path")
    if not session_id or not transcript_path:
        entry["tokens"] = dict(_EMPTY_MEASURED_TOKENS)
        entry["role_usage"] = []
        entry["model_usage"] = []
        return

    import usage_reader
    usage = usage_reader.read_transcript_usage(
        transcript_path, entry.get("started_at"), entry.get("ended_at"), skill)
    if usage.get("degraded"):
        # A failed measurement must never look like a successful one.
        entry["tokens"] = dict(_EMPTY_MEASURED_TOKENS)
        entry["role_usage"] = []
        entry["model_usage"] = []
        return
    entry["role_usage"] = usage.get("role_usage") or []
    entry["model_usage"] = usage.get("model_usage") or []
    entry["tokens"] = _sum_role_tokens(entry["role_usage"])


def elapsed_seconds(start, end):
    """Wall-clock `end - start` in whole seconds, or None for a missing/malformed/
    inverted interval — a true zero-length interval returns 0, distinguishable
    from "unknown"."""
    start_dt, end_dt = parse_iso(start), parse_iso(end)
    if start_dt and end_dt and end_dt >= start_dt:
        return int((end_dt - start_dt).total_seconds())
    return None


def run_seconds(entry):
    """Adapter: elapsed_seconds over a run entry's started_at/ended_at."""
    return elapsed_seconds(entry.get("started_at"), entry.get("ended_at"))


def compute_ticket_totals(tdir):
    """Roll up time and tokens across every skill state file in the partition.

    A None-elapsed run (missing/malformed/inverted interval) is excluded from
    working_seconds rather than counted as zero, but still counts in runs and
    in exactly one of runs_timed/runs_untimed. A cost field a pre-ADR-0103
    entry still carries is ignored."""
    totals = {
        # `invocations`, not `runs`: a "run" is the whole workflow over a
        # subject now, and what this counts is a SESSION's attempt at one step.
        # Two different things under one name is how a metric starts lying.
        "invocations": 0, "working_seconds": 0,
        "tokens": {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0},
        "runs_timed": 0, "runs_untimed": 0,
    }
    for skill in HOOKED_SKILLS:
        state = read_json(state_path(tdir, skill))
        if not isinstance(state, dict):
            continue
        # `invocations`, not `runs`: the partition is a run now, so a `runs`
        # array inside a step would mean the wrong thing (§4.4).
        for entry in state.get("invocations") or []:
            if not isinstance(entry, dict):
                continue
            totals["invocations"] += 1
            seconds = run_seconds(entry)
            if seconds is None:
                totals["runs_untimed"] += 1
            else:
                totals["runs_timed"] += 1
                totals["working_seconds"] += seconds
            tokens = entry.get("tokens") or {}
            for field in _TOKEN_TOTAL_FIELDS:
                totals["tokens"][field] += int(tokens.get(field, 0) or 0)
    return totals


def metrics_path(workspace, repo_id):
    return os.path.join(repo_dir(workspace, repo_id), "metrics.json")


def update_metrics(workspace, repo_id, run_entry=None, pr_created=False, pr_merged=False, pr_number=None):
    """Repo-level aggregates: ticket counts recomputed from the index (idempotent),
    PR counts and run totals accumulated incrementally."""
    def _write():
        return _update_metrics_body(workspace, repo_id, run_entry, pr_created, pr_merged, pr_number)

    return _guarded_repo_write(workspace, repo_id, "metrics.json.lock", _write)


def _update_metrics_body(workspace, repo_id, run_entry, pr_created, pr_merged, pr_number):
    path = metrics_path(workspace, repo_id)
    data = read_json(path) or {}
    data.setdefault("tickets", {})
    data.setdefault("prs", {"created": 0, "merged": 0, "created_pr_numbers": []})
    data.setdefault("totals", {
        "runs": 0, "working_seconds": 0,
        "tokens": {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0},
        "runs_timed": 0, "runs_untimed": 0,
    })
    # A pre-existing metrics.json predates these counters; backfill them at 0.
    # Cost and API-duration totals an older file carries are left as they
    # are and no longer accumulate (ADR-0103).
    for counter in ("runs_timed", "runs_untimed"):
        data["totals"].setdefault(counter, 0)
    # A pre-existing metrics.json's tokens dict predates the cache fields; backfill at 0.
    data["totals"].setdefault("tokens", {})
    for field in _TOKEN_TOTAL_FIELDS:
        data["totals"]["tokens"].setdefault(field, 0)

    index = read_json(index_path(workspace, repo_id)) or {"tickets": {}}
    by_status = {}
    by_type = {}
    for ticket in index.get("tickets", {}).values():
        by_status[ticket.get("status") or "unknown"] = by_status.get(ticket.get("status") or "unknown", 0) + 1
        by_type[ticket.get("type") or "unknown"] = by_type.get(ticket.get("type") or "unknown", 0) + 1
    data["tickets"] = {"total": len(index.get("tickets", {})), "by_status": by_status, "by_type": by_type}

    if pr_created:
        numbers = data["prs"].setdefault("created_pr_numbers", [])
        if isinstance(pr_number, int) and pr_number > 0 and pr_number not in numbers:
            numbers.append(pr_number)
            numbers.sort()
            data["prs"]["created"] = len(numbers)
        # else: leave both created and created_pr_numbers unchanged (idempotent)
    if pr_merged:
        data["prs"]["merged"] = int(data["prs"].get("merged", 0)) + 1
    if run_entry:
        totals = data["totals"]
        totals["runs"] = int(totals.get("runs", 0)) + 1
        seconds = run_seconds(run_entry)
        if seconds is None:
            totals["runs_untimed"] = int(totals.get("runs_untimed", 0)) + 1
        else:
            totals["runs_timed"] = int(totals.get("runs_timed", 0)) + 1
            totals["working_seconds"] = int(totals.get("working_seconds", 0)) + seconds
        tokens = run_entry.get("tokens") or {}
        totals.setdefault("tokens", {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0})
        for field in _TOKEN_TOTAL_FIELDS:
            totals["tokens"][field] = int(totals["tokens"].get(field, 0)) + int(tokens.get(field, 0) or 0)
    data["updated_at"] = now_iso()
    write_json(path, data)
    return data



def backfill_distinct_pr_count(workspace, repo_id):
    """One-time idempotent recompute of prs.created_pr_numbers from distinct
    positive states.pr.number values across all active and archive/ ticket
    partitions.  Sets prs.created = len(created_pr_numbers).

    Read-only except the single metrics.json write.  Safe to re-run: the result
    is always the recoverable distinct set from the current partition state; a
    second run with unchanged partitions produces the identical output.

    Per clarification C-1 (MAR-13 / MAR-8 design A1): pre-fix history without
    a retained PR number is unrecoverable and accepted -- this is not a defect.
    """
    # Gather all ticket IDs from the index
    idx = read_json(index_path(workspace, repo_id)) or {"tickets": {}}
    ticket_ids = list(idx.get("tickets", {}).keys())

    distinct_numbers = set()
    for tid in ticket_ids:
        # A ticket's PRs are its RUNS' PRs: the run whose subject is this
        # ticket is where create-pr wrote.
        from .run import partition_for_ticket
        tdir, _archived = partition_for_ticket(repo_dir(workspace, repo_id), tid)
        sp = state_path(tdir, "create-pr")
        state = read_json(sp)
        if not isinstance(state, dict):
            continue
        pr_num = (state.get("states") or {}).get("pr", {})
        if isinstance(pr_num, dict):
            pr_num = pr_num.get("number")
        if isinstance(pr_num, int) and pr_num > 0:
            distinct_numbers.add(pr_num)

    # Write back -- overwrite is what makes this idempotent
    mpath = metrics_path(workspace, repo_id)
    data = read_json(mpath) or {}
    data.setdefault("prs", {"created": 0, "merged": 0, "created_pr_numbers": []})
    recovered = sorted(distinct_numbers)
    data["prs"]["created_pr_numbers"] = recovered
    data["prs"]["created"] = len(recovered)
    write_json(mpath, data)
    return data
