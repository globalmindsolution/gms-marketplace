#!/usr/bin/env python3
"""metrics_aggregate.py — read-only seven-panel dashboard aggregator for /acs:metrics (MAR-5).

Stdlib-only (Python 3.9+, no pip). Reads the current repo's workspace artifacts and prints ONE
aggregate JSON object to stdout:

    {
      "panels": {
        "1": {...}, "2": {...}, "3": {...}, "4": {...}, "5": {...}, "6": {...}, "7": {...},
        "delivery_summary": {...}, "issues": [...], "progress": {...},
        "deadline": {...}, "usage_summary": {...}
      },
      "meta": {"generated_at": "<ISO8601>", "repo_id": "...", "ticket_count": <int>,
               "degraded": [{"ticket_id": "...", "panel": <int|str>, "reason": "..."}, ...]}
    }

Design A1 (helper emits aggregate JSON; the SKILL renders show_widget — ZERO show_widget
dependency here), B1 (every panel key "1".."7" PLUS the five new string keys is ALWAYS present;
degradation is a "no data" marker inside the panel plus a meta.degraded entry, never a missing
key), C1 (panel 6 token-burn buckets sourced from each HOOKED_SKILLS run entry's measured
`role_usage` field (acs_lib.finalize_run), bucketed by role string as-is — this now
includes a `coordinator` bucket, resolving the former ledger C-5 exclusion; panel 5 review
iterations from code-state states.review.iterations authoritative with the max
verify-XML-iteration fallback), D1 (bounded single pass: enumerate tickets from
tickets-index.json, resolve each partition active-then-archive, read the four state files once
each, plus each HOOKED_SKILLS `<skill>-state.json` for role_usage; xml.etree is a documented
reserved fallback, not used by default).

New panel keys (MAR-14 spec 01):
  "delivery_summary" — PM KPIs: done/total, prs_merged, avg lead/cycle, coverage_pass_rate.
  "issues"           — sorted list of all index entries with id, title, status, type, external_key.
  "progress"         — overall done/total, per_epic breakdown, burn_up date series.
  "deadline"         — always degraded "not set" frame (Child 3 / MAR-15 wires real data).
  "usage_summary"    — totals + four averages from panel3; mirrors usage view data needs.

New panel key (MAR-3 spec 04):
  "usage_by_model"   — per-model token/cost breakdown, at repo AND per-ticket scope, folded
                        from each run entry's model_usage field (acs_lib._measure_run_usage)
                        in the same single pass _accumulate_burn already makes for panel 6
                        (zero additional file reads). "no data" repo/ticket-row when no
                        contributing run entry anywhere carries model_usage (legacy history).

New panel key (MAR-4 spec 01):
  "usage_by_ticket"  — per-ticket role-share percentages: panel 6's bucket widens to the four
                        token classes plus repo-scope token_share_pct/cost_share_pct; this panel
                        adds the SAME shares at ticket scope, keyed by role, in the same
                        _accumulate_burn pass (zero additional file reads). "no data" ticket row
                        when the ticket contributed no role_usage anywhere.

Per-skill/per-run API-duration surfacing (MAR-7 spec 01): panel 3 gains "step_api_duration"/
"step_order" additive sibling keys per ticket ("steps" itself unchanged); "usage_by_ticket"
widens with ticket/skill-scoped api_duration_ms/api_duration_basis and a skills[] array;
"usage_summary" gains total_api_duration_ms and its two per-ticket/per-pr averages. All sourced
from fields MAR-6 already persists — zero additional file reads.

Existing panel keys "1".."7" and their shapes are UNCHANGED (A1 contract). New keys are additive.
meta.degraded entries for new panels use string panel names; entries for "1".."7" use integers.

The helper is READ-ONLY: zero acs_lib.write_json calls; it mutates no workspace file.

Factoring (spec 01 contract): aggregate(workspace, repo_id) -> dict is a PURE function (no git,
no settings, no stdout) and is the test + coverage entry point; main() is a thin smoke path that
resolves {workspace, repo_id} via acs_lib.build_context(), calls aggregate(), and prints the JSON.
"""

import glob
import json
import os
import re
import sys
# The scripts dir must be on sys.path BEFORE the first import that needs
# it -- acs_lib and every sibling below. Inverting this (the insert after
# the imports) leaves the statement dead and makes loading this file by
# absolute path raise ModuleNotFoundError; every current caller happens to
# have the dir on sys.path already, which is why CI stayed green.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib  # noqa: E402

# The module split (MAR-531) is invisible to every caller: this file stays the
# entry point /acs:metrics and /acs:usage invoke and the module the tests
# import, and re-exports the whole pre-split surface -- private helpers
# included, because the tests reach them by name. Import from the module that
# OWNS a name when you add code; import from here only to keep a caller working.
from metrics_aggregate_common import (PANEL_KEYS, _ITER_RE, _NEW_PANEL_KEYS,
    _elapsed_seconds, _is_number, _parse_due_date,
    _read_text, _safe_avg, _share_pct, _to_int)  # noqa: F401
from metrics_aggregate_panels import (_deadline_panel, _delivery_summary,
    _escalations_tally, _issues_panel, _progress_panel,
    _usage_summary_panel)  # noqa: F401
from metrics_aggregate_usage import (_apply_panel6_shares, _empty_model_bucket,
    _empty_panel6_bucket, _empty_skill_duration_bucket,
    _finalize_model_bucket,
    _finalize_role_ticket_bucket,
    _finalize_skill_bucket, _fold_model_bucket,
    _usage_by_model_panel, _usage_by_ticket_panel)  # noqa: F401
from metrics_aggregate_rows import (_accumulate_burn, _accumulate_funnel,
    _max_verify_iteration, _panel1, _panel3_row,
    _panel4_row, _panel5_row, _panel7, _panel7_row,
    _rework_count, _test_runs_source)  # noqa: F401



def aggregate(workspace, repo_id, now=None):
    """Pure aggregator: read the workspace partition for `repo_id`, return the dashboard payload.

    now: optional ISO-8601 string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ) pinning the reference
    instant for both meta.generated_at AND the deadline comparison.  When None (default),
    acs_lib.now_iso() is called once and reused for both.  Passing a fixed value yields
    deterministic, byte-identical output for the same workspace state (AC-6, C-1).

    Never raises on missing/partial state — each absent source becomes a "no data" marker plus a
    meta.degraded entry. No git, no settings, no stdout, no writes.

    Returns the 7 existing panel keys ("1".."7") PLUS 5 new string keys
    ("delivery_summary", "issues", "progress", "deadline", "usage_summary")
    all at the same nesting level inside "panels". The new keys are additive; the existing
    panel shapes are UNCHANGED (A1 contract, MAR-8/design.md:88,456-458).
    """
    # C-1: one reference instant used for BOTH meta.generated_at AND deadline comparison.
    _now_str = now if now is not None else acs_lib.now_iso()
    degraded = []

    def degrade(ticket_id, panel, reason):
        degraded.append({"ticket_id": ticket_id, "panel": panel, "reason": reason})

    index = acs_lib.read_json(acs_lib.index_path(workspace, repo_id))
    tickets = (index or {}).get("tickets") if isinstance(index, dict) else None
    tickets = tickets if isinstance(tickets, dict) else {}

    repo_metrics = acs_lib.read_json(acs_lib.metrics_path(workspace, repo_id))
    repo_metrics = repo_metrics if isinstance(repo_metrics, dict) else None

    meta = {
        "generated_at": _now_str,
        "repo_id": repo_id,
        "ticket_count": len(tickets),
        "degraded": degraded,
    }

    # Empty workspace (no tickets enumerated): every panel "no data", exit-0 path. B1 keeps all keys.
    if not tickets:
        all_keys = list(PANEL_KEYS) + list(_NEW_PANEL_KEYS)
        return {
            "panels": {k: "no data" for k in all_keys},
            "meta": meta,
            "test_runs": _test_runs_source(workspace, repo_id, degrade),
        }

    # Panel 1 — throughput by status/type (repo metrics primary; recompute fallback from the index).
    panel1 = _panel1(tickets, repo_metrics)

    # Panels 2/3 funnel + cost/time, 4 coverage, 5 review iterations, 6 token burn — single pass.
    funnel = {skill: 0 for skill in acs_lib.HOOKED_SKILLS}
    p3_rows = []
    p4_rows = []
    p5_rows = []
    p7_rows = []
    burn = {role: _empty_panel6_bucket()
            for role in ("planner", "executor", "verifier", "coordinator")}
    repo_models = {}  # model -> raw accumulator (MAR-3: usage_by_model repo scope)
    _ticket_model_rows = []  # [(ticket_id, {model -> raw accumulator}), ...] (ticket scope)
    _ticket_role_rows = []  # [(ticket_id, {role -> raw accumulator}), ...] (MAR-4: usage_by_ticket)
    _ticket_skill_rows = []  # [(ticket_id, {skill -> raw duration accumulator}), ...] (MAR-7)

    # Per-ticket extra data collected for the new panels (no additional file reads — reuses
    # the ticket.json and pipeline-state.json already opened below; spec 01:44-49).
    # _ticket_updated_at: {ticket_id -> updated_at str or None} for burn_up fallback (spec 01:198-202)
    _ticket_updated_at = {}
    # _merge_ended_at: {ticket_id -> ended_at str or None} for burn_up primary date (spec 01:193-197)
    _merge_ended_at = {}
    # _tickets_due_data: [{id, due_date, status}] for deadline panel (spec 02)
    _tickets_due_data = []
    # _escalations_by_ticket: {ticket_id -> [event, ...]} unioned across a ticket's runs
    # (MAR-109 spec 01; code_state already read below for panels 4/5 — no extra file read).
    _escalations_by_ticket = {}

    for ticket_id in tickets:
        tdir, _archived = acs_lib.find_ticket_partition(workspace, repo_id, ticket_id)

        pipeline = acs_lib.read_json(os.path.join(tdir, "pipeline-state.json"))
        if isinstance(pipeline, dict):
            _accumulate_funnel(funnel, pipeline)
        else:
            degrade(ticket_id, 2, "pipeline-state.json absent — ticket omitted from the funnel")
            degrade(ticket_id, 3, "pipeline-state.json absent — no cost/time row")

        # Collect merge-pr.ended_at for burn_up (primary date source; spec 01:193-197).
        steps = pipeline.get("steps") if isinstance(pipeline, dict) else None
        steps = steps if isinstance(steps, dict) else {}
        merge_step = steps.get("merge-pr")
        _merge_ended_at[ticket_id] = merge_step.get("ended_at") if isinstance(merge_step, dict) else None

        code_state = acs_lib.read_json(acs_lib.state_path(tdir, "code"))
        p4_rows.append(_panel4_row(ticket_id, code_state, degrade))
        p5_rows.append(_panel5_row(ticket_id, tdir, code_state, degrade))

        # Collect escalation events across all of this ticket's runs (spec 01:73-81).
        runs = code_state.get("runs") if isinstance(code_state, dict) else None
        events = []
        for run in (runs or []):
            if isinstance(run, dict):
                events.extend(run.get("escalations") or [])
        if events:
            _escalations_by_ticket[ticket_id] = events

        p7_rows.append(_panel7_row(ticket_id, tdir, pipeline, degrade))

        ticket_models, ticket_roles, ticket_skills = _accumulate_burn(burn, tdir)
        if isinstance(pipeline, dict):
            p3_rows.append(_panel3_row(ticket_id, pipeline, ticket_skills))
        for model, bucket in ticket_models.items():
            repo_bucket = repo_models.setdefault(model, _empty_model_bucket())
            _fold_model_bucket(repo_bucket, bucket)
        _ticket_model_rows.append((ticket_id, ticket_models))
        _ticket_role_rows.append((ticket_id, ticket_roles))
        _ticket_skill_rows.append((ticket_id, ticket_skills))

        # Collect ticket.json.updated_at for burn_up fallback (spec 01:198-202).
        # ticket.json is already opened in _panel7_row (read-only, no extra I/O cost).
        ticket_json = acs_lib.read_json(os.path.join(tdir, "ticket.json"))
        _ticket_updated_at[ticket_id] = (
            ticket_json.get("updated_at") if isinstance(ticket_json, dict) else None
        )

        # Collect due_date + status for the deadline panel (spec 02: reuse already-open ticket.json).
        _due_date_raw = ticket_json.get("due_date") if isinstance(ticket_json, dict) else None
        # Status can come from the index entry (already in memory; no extra I/O) or ticket_json.
        _tkt_status = tickets[ticket_id].get("status") if isinstance(tickets[ticket_id], dict) else None
        _tickets_due_data.append({
            "id": ticket_id,
            "due_date": _due_date_raw,
            "status": _tkt_status,
        })

    prs = (repo_metrics or {}).get("prs", {"created": 0, "merged": 0})
    totals = (repo_metrics or {}).get("totals", {})
    merged = prs.get("merged") if isinstance(prs, dict) else None
    working_seconds = totals.get("working_seconds") if isinstance(totals, dict) else None
    cost_usd = totals.get("cost_usd") if isinstance(totals, dict) else None
    ticket_count = meta["ticket_count"]

    panel2 = {"steps": funnel, "prs": prs}
    panel3 = {
        "tickets": p3_rows,
        "repo_totals": totals,
        "averages": {
            "avg_working_seconds_per_ticket": _safe_avg(working_seconds, ticket_count),
            "avg_working_seconds_per_pr": _safe_avg(working_seconds, merged),
            "avg_cost_per_ticket": _safe_avg(cost_usd, ticket_count),
            "avg_cost_per_pr": _safe_avg(cost_usd, merged),
        },
    }
    panel4 = {"tickets": p4_rows}
    panel5 = {"tickets": p5_rows}
    _apply_panel6_shares(burn)  # repo-scope token_share_pct/cost_share_pct, once (MAR-4 spec 01)
    panel6 = burn
    panel7 = _panel7(p7_rows)

    # ---- New panels (MAR-14 spec 01) ----

    # delivery_summary: 5 PM KPIs + additive escalations sub-object (MAR-109 D5)
    delivery_summary = _delivery_summary(
        tickets, prs, panel7, p4_rows, degrade, _escalations_by_ticket
    )

    # issues: sorted list of all index entries (spec 01:129-149)
    issues = _issues_panel(tickets)

    # progress: overall, per_epic, burn_up date series (spec 01:151-229)
    progress = _progress_panel(
        tickets, _merge_ended_at, _ticket_updated_at, degrade
    )

    # deadline: derive on-track/overdue from due_date vs _now_str (spec 02 / MAR-15).
    _now_date = _parse_due_date(_now_str)  # date object for comparison; None if now is None
    deadline = _deadline_panel(_tickets_due_data, _now_date, degrade)

    # usage_summary: totals + four averages (spec 01:251-269), + 3 API-duration fields (MAR-7)
    usage_summary = _usage_summary_panel(totals, prs, panel3["averages"], ticket_count)

    # usage_by_model: per-model token/cost breakdown, repo + per-ticket (MAR-3 spec 04)
    usage_by_model = _usage_by_model_panel(repo_models, _ticket_model_rows)

    # usage_by_ticket: per-ticket role-share percentages (MAR-4 spec 01), widened with
    # ticket/skill-scoped API duration + a skills[] array (MAR-7 spec 01)
    usage_by_ticket = _usage_by_ticket_panel(_ticket_role_rows, _ticket_skill_rows)

    panels = {
        "1": panel1, "2": panel2, "3": panel3, "4": panel4, "5": panel5,
        "6": panel6, "7": panel7,
        "delivery_summary": delivery_summary,
        "issues": issues,
        "progress": progress,
        "deadline": deadline,
        "usage_summary": usage_summary,
        "usage_by_model": usage_by_model,
        "usage_by_ticket": usage_by_ticket,
    }
    return {
        "panels": panels,
        "meta": meta,
        "test_runs": _test_runs_source(workspace, repo_id, degrade),
    }


def main():
    """Thin smoke path: resolve {workspace, repo_id} via build_context, aggregate, print JSON."""
    ctx = acs_lib.build_context(os.getcwd())
    result = aggregate(ctx["workspace"], ctx["repo_id"])
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
