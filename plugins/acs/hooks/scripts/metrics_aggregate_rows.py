"""metrics_aggregate_rows — the per-ticket row builders for panels 1, 3-5 and 7
(extracted from metrics_aggregate.py by MAR-531).

One function per panel row, plus the funnel and burn accumulators the main loop
calls once per ticket.
"""


import glob
import json
import os
import re
import sys
import acs_lib  # noqa: E402

from metrics_aggregate_common import _ITER_RE, _elapsed_seconds, _is_number, _read_text, _safe_avg, _to_int
from metrics_aggregate_usage import _empty_model_bucket, _empty_panel6_bucket, _empty_skill_duration_bucket



def _test_runs_source(workspace, repo_id, degrade):
    """Read-only test-runs/*/results.json source (MAR-114 spec 03).

    Additive, absence-tolerant, malformed-tolerant, read-only: folds run count and the
    most-recent run's suite pass/fail counts + regressions[].action tally into a new
    top-level "test_runs" key (sibling to "panels"/"meta") without touching PANEL_KEYS
    or _NEW_PANEL_KEYS. "no data" when the directory is absent/empty or every run present
    fails to parse as a dict (each unparseable run also gets a meta.degraded entry).
    """
    pattern = os.path.join(workspace, repo_id, "test-runs", "*", "results.json")
    run_paths = sorted(glob.glob(pattern))
    if not run_paths:
        return "no data"

    runs = []
    for path in run_paths:
        run_id = os.path.basename(os.path.dirname(path))
        data = acs_lib.read_json(path)
        if not isinstance(data, dict):
            degrade(None, "test_runs", "unparseable test-runs/%s/results.json — treated as no data" % run_id)
            continue
        runs.append((run_id, data))

    if not runs:
        return "no data"

    runs.sort(key=lambda pair: pair[0])
    latest_id, latest = runs[-1]

    suites = latest.get("suites") if isinstance(latest.get("suites"), list) else []
    passed = sum(1 for s in suites if isinstance(s, dict) and s.get("status") == "pass")
    failed = sum(1 for s in suites if isinstance(s, dict) and s.get("status") == "fail")

    regressions = latest.get("regressions") if isinstance(latest.get("regressions"), list) else []
    action_tally = {}
    for reg in regressions:
        if isinstance(reg, dict):
            action = reg.get("action")
            if action:
                action_tally[action] = action_tally.get(action, 0) + 1

    return {
        "runs_observed": len(runs),
        "latest_run_id": latest_id,
        "latest_suites_passed": passed,
        "latest_suites_failed": failed,
        "latest_regressions_by_action": action_tally,
    }


# ---------------------------------------------------------------------------
# Existing panel builders (unchanged)
# ---------------------------------------------------------------------------

def _panel1(tickets, repo_metrics):
    """Throughput by status/type: prefer metrics.json.tickets; recompute from the index otherwise."""
    if isinstance(repo_metrics, dict):
        tmetrics = repo_metrics.get("tickets")
        if isinstance(tmetrics, dict) and (tmetrics.get("by_status") or tmetrics.get("by_type")):
            return {"by_status": tmetrics.get("by_status", {}), "by_type": tmetrics.get("by_type", {})}
    by_status = {}
    by_type = {}
    for t in tickets.values():
        if not isinstance(t, dict):
            continue
        st = t.get("status")
        ty = t.get("type")
        if st is not None:
            by_status[st] = by_status.get(st, 0) + 1
        if ty is not None:
            by_type[ty] = by_type.get(ty, 0) + 1
    return {"by_status": by_status, "by_type": by_type}


def _accumulate_funnel(funnel, pipeline):
    steps = pipeline.get("steps")
    if not isinstance(steps, dict):
        return
    for skill in funnel:
        step = steps.get(skill)
        if isinstance(step, dict) and step.get("status") == "completed":
            funnel[skill] += 1


def _panel3_row(ticket_id, pipeline, ticket_skills=None):
    """Panel-3 row: ticket_id/steps/totals unchanged (F13's no-mutation invariant -- `steps` is
    only ever read here, never reordered or filtered), plus two additive sibling keys (MAR-7
    spec 01, D5.4/S-C): step_api_duration (per-skill API duration + basis) and step_order (the
    ordered union of steps' and step_api_duration's own key sets, K-A).

    ticket_skills: the SAME raw {skill -> duration accumulator} map _accumulate_burn returns --
    zero extra file reads (P-1). A skill's step_api_duration cell's "basis" passes through the
    LAST contributing run's own literal basis (not the "apportioned"/"unavailable" collapse
    _finalize_skill_bucket uses for usage_by_ticket.skills[] -- that scope's own roll-up rule).
    """
    steps = pipeline.get("steps") if isinstance(pipeline.get("steps"), dict) else {}
    per_step = {}
    for skill, step in steps.items():
        if isinstance(step, dict):
            per_step[skill] = acs_lib.run_seconds(step)
    totals = pipeline.get("totals") if isinstance(pipeline.get("totals"), dict) else {}

    ticket_skills = ticket_skills if isinstance(ticket_skills, dict) else {}
    step_api_duration = {}
    for skill, bucket in ticket_skills.items():
        if not bucket.get("api_duration_seen"):
            continue
        contributing = [r for r in bucket.get("runs", []) if _is_number(r.get("api_duration_ms"))]
        basis = contributing[-1]["api_duration_basis"] if contributing else "unavailable"
        step_api_duration[skill] = {"ms": round(bucket["api_duration_ms_sum"], 4), "basis": basis}

    union = set(per_step) | set(step_api_duration)
    step_order = ([s for s in acs_lib.PIPELINE_STEP_ORDER if s in union]
                  + sorted(union - set(acs_lib.PIPELINE_STEP_ORDER)))

    return {
        "ticket_id": ticket_id,
        "steps": per_step,
        "totals": totals,
        "step_api_duration": step_api_duration,
        "step_order": step_order,
    }


def _panel4_row(ticket_id, code_state, degrade):
    states = code_state.get("states") if isinstance(code_state, dict) else None
    tests = states.get("tests") if isinstance(states, dict) else None
    if not isinstance(tests, dict):
        degrade(ticket_id, 4, "code-state.json (states.tests) absent — coverage unavailable")
        return {"ticket_id": ticket_id, "cell": "no data"}
    achieved = tests.get("coverage_percent")
    target = tests.get("coverage_target")
    if not isinstance(achieved, (int, float)) or isinstance(achieved, bool) or not isinstance(target, (int, float)) or isinstance(target, bool):
        degrade(ticket_id, 4, "coverage_percent null or coverage_target non-numeric — no coverage cell")
        return {"ticket_id": ticket_id, "cell": "no data"}
    return {
        "ticket_id": ticket_id,
        "achieved": achieved,
        "target": target,
        "passed": bool((states or {}).get("verifier_passed")),
    }


def _panel5_row(ticket_id, tdir, code_state, degrade):
    states = code_state.get("states") if isinstance(code_state, dict) else None
    review = states.get("review") if isinstance(states, dict) else None
    if isinstance(review, dict) and isinstance(review.get("iterations"), int):
        return {"ticket_id": ticket_id, "iterations": review["iterations"]}
    # fallback: max iteration among phases/code/iter-N-verify.xml result files
    max_iter = _max_verify_iteration(tdir)
    if max_iter is not None:
        return {"ticket_id": ticket_id, "iterations": max_iter}
    degrade(ticket_id, 5, "no review.iterations and no code/iter-*-verify.xml — iterations unknown")
    return {"ticket_id": ticket_id, "iterations": "no data"}


def _rework_count(tdir):
    """Count distinct positive PR numbers from create-pr-state.json in the resolved partition.

    Reads `state_path(tdir, 'create-pr')` (i.e. <tdir>/create-pr-state.json) and collects
    distinct positive integers from:
      - data["states"]["pr"]["number"] (the current/latest PR number)
      - data["runs"][i]["pr"]["number"] for each run entry (historical PR numbers)

    Returns len({n for n in numbers if isinstance(n, int) and n > 0}).
    Returns 0 on any error: missing file, missing keys, malformed JSON — consistent with the
    B1 "missing input -> no data, never crash" invariant (design.md lines 89-97).
    This function is read-only: it never writes to disk.
    """
    path = acs_lib.state_path(tdir, "create-pr")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return 0

    if not isinstance(data, dict):
        return 0

    numbers = set()

    # Collect from states.pr.number (current PR)
    try:
        n = data["states"]["pr"]["number"]
        if isinstance(n, int) and not isinstance(n, bool) and n > 0:
            numbers.add(n)
    except (KeyError, TypeError):
        pass

    # Collect from runs[i].pr.number (historical PRs across all runs)
    runs = data.get("runs")
    if isinstance(runs, list):
        for run in runs:
            try:
                n = run["pr"]["number"]
                if isinstance(n, int) and not isinstance(n, bool) and n > 0:
                    numbers.add(n)
            except (KeyError, TypeError):
                pass

    return len(numbers)


def _panel7_row(ticket_id, tdir, pipeline, degrade):
    """Per-ticket lead/cycle wall-clock seconds (AC-2). Reads ticket.json.created_at (read-only).

    lead  = merge-pr.ended_at - ticket.json.created_at
    cycle = merge-pr.ended_at - code.started_at
    End anchor is merge-pr (NOT create-pr); value is wall-clock elapsed (NOT working_seconds).
    A value that cannot be computed is the string "no data" plus a panel-7 meta.degraded entry.

    Overlap-safe guarantee (spec 02 / design B1): aggregate() never raises on overlapping or
    re-cycled spans. When code.started_at falls after merge-pr.ended_at (cycle inversion) or
    ticket.created_at falls after merge-pr.ended_at (lead inversion), _elapsed_seconds returns
    None, cycle_seconds / lead_seconds is set to "no data", and the ticket id is appended to
    meta.degraded (panel 7). One row is always returned per ticket; nothing is written.

    rework_count (spec 02 AC-8): per-ticket count of distinct positive PR numbers recoverable
    from create-pr-state.json in the resolved partition (tdir). Additive field; always an int
    >= 0; not averaged. Never raises: missing or malformed state files contribute 0.
    """
    ticket = acs_lib.read_json(os.path.join(tdir, "ticket.json"))
    created_at = ticket.get("created_at") if isinstance(ticket, dict) else None

    steps = pipeline.get("steps") if isinstance(pipeline, dict) else None
    steps = steps if isinstance(steps, dict) else {}
    merge_step = steps.get("merge-pr")
    merge_ended = merge_step.get("ended_at") if isinstance(merge_step, dict) else None
    code_step = steps.get("code")
    code_started = code_step.get("started_at") if isinstance(code_step, dict) else None

    lead = _elapsed_seconds(created_at, merge_ended)
    cycle = _elapsed_seconds(code_started, merge_ended)

    # Degrade reasons (B1): emit the open-ticket reason alone when there is no merge-pr.ended_at
    # (both unavailable for one root cause); otherwise emit at most one reason per missing input.
    if acs_lib.parse_iso(merge_ended) is None:
        degrade(ticket_id, 7, "no merged PR — lead/cycle in progress")
    else:
        if lead is None:
            degrade(ticket_id, 7, "no ticket created_at — lead unavailable")
        if cycle is None:
            degrade(ticket_id, 7, "no code step — cycle unavailable")

    return {
        "ticket_id": ticket_id,
        "lead_seconds": lead if lead is not None else "no data",
        "cycle_seconds": cycle if cycle is not None else "no data",
        "rework_count": _rework_count(tdir),
    }


def _panel7(p7_rows):
    """Assemble panel 7: per-ticket rows plus averages over the subset with a numeric value.

    rework_count is a per-ticket count field, not a duration — it is not averaged here.
    Only lead_seconds and cycle_seconds contribute to the panel-level averages.
    """
    leads = [r["lead_seconds"] for r in p7_rows if _is_number(r["lead_seconds"])]
    cycles = [r["cycle_seconds"] for r in p7_rows if _is_number(r["cycle_seconds"])]
    return {
        "tickets": p7_rows,
        "avg_lead_seconds": _safe_avg(sum(leads), len(leads)),
        "avg_cycle_seconds": _safe_avg(sum(cycles), len(cycles)),
    }


def _max_verify_iteration(tdir):
    best = None
    for path in glob.glob(os.path.join(tdir, "phases", "code", "iter-*-verify.xml")):
        match = _ITER_RE.search(_read_text(path))
        if match:
            n = int(match.group(1))
            best = n if best is None else max(best, n)
    return best


def _accumulate_burn(burn, tdir):
    """Sum each HOOKED_SKILLS run entry's measured `role_usage` into role buckets (panel 6, now
    widened to the four token classes, MAR-4 spec 01), this ticket's OWN role_usage into a raw
    per-role accumulator (usage_by_ticket, MAR-4 spec 01), this ticket's `model_usage` into
    per-model buckets (usage_by_model, MAR-3 spec 04), and each entry's own `api_duration_ms`/
    `api_duration_basis`/wall-clock seconds into a raw per-skill duration accumulator (panel 3's
    step_api_duration + usage_by_ticket.skills[], MAR-7 spec 01, D5.4/P-1 -- zero additional
    file reads).

    Reads acs_lib.finalize_run's own persisted shape directly instead of scraping the retired
    <metrics> XML element; a role bucket is created on first use (dict.setdefault), so
    `coordinator` now surfaces like any other role instead of being silently excluded.
    `burn`'s shape and behavior are unchanged (widened, not reshaped); the model/role/skill
    accumulators are this function's return value -- (ticket_models, ticket_roles, ticket_skills).
    """
    ticket_models = {}
    ticket_roles = {}
    ticket_skills = {}
    for skill in acs_lib.HOOKED_SKILLS:
        state = acs_lib.read_json(acs_lib.state_path(tdir, skill))
        if not isinstance(state, dict):
            continue
        for entry in state.get("runs") or []:
            if not isinstance(entry, dict):
                continue

            skill_bucket = ticket_skills.setdefault(skill, _empty_skill_duration_bucket())
            wall_clock_seconds = acs_lib.run_seconds(entry)
            if wall_clock_seconds is not None:
                skill_bucket["run_seconds_sum"] += wall_clock_seconds
                skill_bucket["run_seconds_seen"] = True
            api_duration_ms = entry.get("api_duration_ms")
            api_duration_basis = entry.get("api_duration_basis") or "unavailable"
            if _is_number(api_duration_ms):
                skill_bucket["api_duration_ms_sum"] += api_duration_ms
                skill_bucket["api_duration_seen"] = True
            skill_bucket["runs"].append({
                "started_at": entry.get("started_at"),
                "wall_clock_seconds": wall_clock_seconds,
                "api_duration_ms": api_duration_ms,
                "api_duration_basis": api_duration_basis,
            })

            for item in entry.get("role_usage") or []:
                if not isinstance(item, dict):
                    continue
                role = item.get("role")
                if not role:
                    continue
                cache_creation = _to_int(item.get("cache_creation"))
                cache_read = _to_int(item.get("cache_read"))
                cost = item.get("cost_usd")

                bucket = burn.setdefault(role, _empty_panel6_bucket())
                bucket["input"] += _to_int(item.get("input"))
                bucket["output"] += _to_int(item.get("output"))
                bucket["cache_creation"] += cache_creation
                bucket["cache_read"] += cache_read
                if _is_number(cost):
                    bucket["cost"] = round(bucket["cost"] + cost, 6)
                    bucket["cost_seen"] = True

                role_bucket = ticket_roles.setdefault(role, _empty_model_bucket())
                role_bucket["input"] += _to_int(item.get("input"))
                role_bucket["output"] += _to_int(item.get("output"))
                role_bucket["cache_creation"] += cache_creation
                role_bucket["cache_read"] += cache_read
                if _is_number(cost):
                    role_bucket["cost_sum"] += cost
                    role_bucket["cost_seen"] = True
            for item in entry.get("model_usage") or []:
                if not isinstance(item, dict):
                    continue
                model = item.get("model")
                if not model:
                    continue
                model_bucket = ticket_models.setdefault(model, _empty_model_bucket())
                model_bucket["input"] += _to_int(item.get("input"))
                model_bucket["output"] += _to_int(item.get("output"))
                model_bucket["cache_creation"] += _to_int(item.get("cache_creation"))
                model_bucket["cache_read"] += _to_int(item.get("cache_read"))
                cost = item.get("cost_usd")
                if _is_number(cost):
                    model_bucket["cost_sum"] += cost
                    model_bucket["cost_seen"] = True
    return ticket_models, ticket_roles, ticket_skills
