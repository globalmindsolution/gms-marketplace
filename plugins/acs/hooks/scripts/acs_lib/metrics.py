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
# The scripts dir, one level up from this package -- sibling helpers
# (claude_code_adapter, usage_reader, cost_sampler) are imported flat.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import claude_code_adapter as cc  # noqa: E402

from ._common import HOOKED_SKILLS, now_iso, parse_iso, read_json, write_json
from .repo import _guarded_repo_write, find_ticket_partition, index_path, repo_dir, state_path



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
    """Persist MEASURED tokens/role_usage/cost onto `entry` -- read from its
    own recorded transcript (usage_reader) and priced via
    cost_sampler.allocate_cost -- rather than trusting a coordinator's
    self-reported result["tokens"]/result["cost_usd"] (AC-3).

    Required short-circuit (Risk R-N): a run entry with no session_id/
    transcript_path (e.g. new-ticket.py's synthetic, immediately-finalized
    create-ticket runs) never performs transcript I/O -- cost_usd=None,
    cost_basis="unavailable", tokens empty.

    `skill` (the run's own skill, as finalize_run received it) is threaded
    through to usage_reader so it can filter main-session attribution to
    this run's own skill only, excluding same-window records attributed to
    a different acs skill."""
    session_id = entry.get("session_id")
    transcript_path = entry.get("transcript_path")
    if not session_id or not transcript_path:
        entry["tokens"] = dict(_EMPTY_MEASURED_TOKENS)
        entry["cost_usd"] = None
        entry["cost_basis"] = "unavailable"
        entry["role_usage"] = []
        entry["model_usage"] = []
        entry["api_duration_ms"] = None
        entry["api_duration_basis"] = "unavailable"
        return

    import usage_reader
    usage = usage_reader.read_transcript_usage(
        transcript_path, entry.get("started_at"), entry.get("ended_at"), skill)
    if usage.get("degraded"):
        # A failed measurement must never look like a successful one: no
        # cost sample may be consumed and no cursor may advance for a run
        # whose transcript read itself is unreliable.
        entry["tokens"] = dict(_EMPTY_MEASURED_TOKENS)
        entry["cost_usd"] = None
        entry["cost_basis"] = "unavailable"
        entry["role_usage"] = []
        entry["model_usage"] = []
        entry["api_duration_ms"] = None
        entry["api_duration_basis"] = "unavailable"
        return
    role_usage = usage.get("role_usage") or []
    model_usage = usage.get("model_usage") or []
    entry["tokens"] = _sum_role_tokens(role_usage)

    checkout_id = entry.get("checkout_id")
    if not checkout_id:
        # Tokens are measured (transcript-only); cost needs the checkout-scoped
        # sample/cursor files this entry has no checkout_id to locate.
        entry["role_usage"] = role_usage
        entry["model_usage"] = model_usage
        entry["cost_usd"] = None
        entry["cost_basis"] = "unavailable"
        entry["api_duration_ms"] = None
        entry["api_duration_basis"] = "unavailable"
        return

    import cost_sampler
    workspace = os.path.dirname(os.path.dirname(tdir))
    repo_id = os.path.basename(os.path.dirname(tdir))
    result = cost_sampler.allocate_cost(
        workspace, repo_id, checkout_id,
        entry.get("started_at"), entry.get("ended_at"), role_usage, model_usage)
    entry["role_usage"] = result["role_usage"]
    entry["model_usage"] = result["model_usage"]
    entry["cost_usd"] = result["cost_usd"]
    entry["cost_basis"] = result["cost_basis"]
    entry["cost_scope"] = result["cost_scope"]
    entry["excluded_cost_usd"] = result["excluded_cost_usd"]
    entry["excluded_token_share"] = result["excluded_token_share"]
    entry["api_duration_ms"] = result["api_duration_ms"]
    entry["api_duration_basis"] = result["api_duration_basis"]
    entry["api_duration_scope"] = result["api_duration_scope"]


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


#: What compute_ticket_totals folds per run entry. Cost and API duration are the
#: same accumulation over different keys (MAR-522): (value, basis, measured
#: counter, unavailable counter). A third measured quantity is a row, not a
#: fourth copy of the branch below.
_MEASURED_FOLDS = (
    ("cost_usd", "cost_basis", "runs_cost_measured", "runs_cost_unavailable"),
    ("api_duration_ms", "api_duration_basis",
     "runs_api_duration_measured", "runs_api_duration_unavailable"),
)


def _fold_measured(totals, entry, value_key, basis_key, measured_key, unavailable_key):
    """Fold one entry's value into totals when its basis says the value is real.

    A basis outside ("measured", "apportioned") -- or a value that is not a
    number -- counts the run as unavailable and contributes nothing, so a
    degraded run can never quietly read as a zero-cost one. bool is excluded
    explicitly: isinstance(True, int) is True in Python, so a stray True would
    otherwise fold in as 1.0."""
    basis = entry.get(basis_key) or "unavailable"
    value = entry.get(value_key)
    if basis in ("measured", "apportioned") and isinstance(value, (int, float)) \
            and not isinstance(value, bool):
        totals[measured_key] += 1
        totals[value_key] += float(value)
    else:
        totals[unavailable_key] += 1


def compute_ticket_totals(tdir):
    """Roll up time/tokens/cost across every skill state file in the partition.

    A None-elapsed run (missing/malformed/inverted interval) is excluded from
    working_seconds rather than counted as zero, but still counts in runs and
    in exactly one of runs_timed/runs_untimed. Likewise, a run whose
    cost_basis is "measured"/"apportioned" contributes its cost_usd and
    counts in runs_cost_measured; every other run (cost_basis "unavailable",
    or absent -- a legacy pre-cutover run, C-11) counts in
    runs_cost_unavailable and contributes nothing to the cost_usd sum."""
    totals = {
        "runs": 0, "working_seconds": 0,
        "tokens": {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}, "cost_usd": 0.0,
        "runs_timed": 0, "runs_untimed": 0, "runs_cost_measured": 0, "runs_cost_unavailable": 0,
        "api_duration_ms": 0.0, "runs_api_duration_measured": 0, "runs_api_duration_unavailable": 0,
    }
    for skill in HOOKED_SKILLS:
        state = read_json(state_path(tdir, skill))
        if not isinstance(state, dict):
            continue
        for entry in state.get("runs") or []:
            if not isinstance(entry, dict):
                continue
            totals["runs"] += 1
            seconds = run_seconds(entry)
            if seconds is None:
                totals["runs_untimed"] += 1
            else:
                totals["runs_timed"] += 1
                totals["working_seconds"] += seconds
            tokens = entry.get("tokens") or {}
            for field in _TOKEN_TOTAL_FIELDS:
                totals["tokens"][field] += int(tokens.get(field, 0) or 0)
            for fold in _MEASURED_FOLDS:
                _fold_measured(totals, entry, *fold)
    for value_key, _basis, _measured, _unavailable in _MEASURED_FOLDS:
        totals[value_key] = round(totals[value_key], 4)
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
        "tokens": {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}, "cost_usd": 0.0,
        "runs_timed": 0, "runs_untimed": 0, "runs_cost_measured": 0, "runs_cost_unavailable": 0,
        "api_duration_ms": 0.0, "runs_api_duration_measured": 0, "runs_api_duration_unavailable": 0,
    })
    # A pre-existing metrics.json predates these counters; backfill them at 0.
    for counter in ("runs_timed", "runs_untimed", "runs_cost_measured", "runs_cost_unavailable",
                     "runs_api_duration_measured", "runs_api_duration_unavailable"):
        data["totals"].setdefault(counter, 0)
    data["totals"].setdefault("api_duration_ms", 0.0)
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
        cost_basis = run_entry.get("cost_basis") or "unavailable"
        cost_usd = run_entry.get("cost_usd")
        if cost_basis in ("measured", "apportioned") and isinstance(cost_usd, (int, float)) \
                and not isinstance(cost_usd, bool):
            totals["runs_cost_measured"] = int(totals.get("runs_cost_measured", 0)) + 1
            totals["cost_usd"] = round(float(totals.get("cost_usd", 0.0)) + float(cost_usd), 4)
        else:
            totals["runs_cost_unavailable"] = int(totals.get("runs_cost_unavailable", 0)) + 1
        api_duration_basis = run_entry.get("api_duration_basis") or "unavailable"
        api_duration_ms = run_entry.get("api_duration_ms")
        if api_duration_basis in ("measured", "apportioned") and isinstance(api_duration_ms, (int, float)) \
                and not isinstance(api_duration_ms, bool):
            totals["runs_api_duration_measured"] = int(totals.get("runs_api_duration_measured", 0)) + 1
            totals["api_duration_ms"] = round(float(totals.get("api_duration_ms", 0.0)) + float(api_duration_ms), 4)
        else:
            totals["runs_api_duration_unavailable"] = int(totals.get("runs_api_duration_unavailable", 0)) + 1
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
        tdir, _archived = find_ticket_partition(workspace, repo_id, tid)
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
