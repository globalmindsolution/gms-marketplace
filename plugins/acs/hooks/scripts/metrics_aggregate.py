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

# Reuse acs_lib (shared scripts dir) the same way the other hooks/scripts do.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acs_lib  # noqa: E402

PANEL_KEYS = ("1", "2", "3", "4", "5", "6", "7")

# New additive panel keys (MAR-14 spec 01, plus usage_by_model from MAR-3 spec 04 and
# usage_by_ticket from MAR-4 spec 01). Not added to PANEL_KEYS (A1 contract preserved).
_NEW_PANEL_KEYS = ("delivery_summary", "issues", "progress", "deadline", "usage_summary",
                    "usage_by_model", "usage_by_ticket")

# iteration="N" on a verify result XML (panel 5 fallback)
_ITER_RE = re.compile(r'\biteration\s*=\s*"(\d+)"')


def _to_int(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _is_number(value):
    """True for a real int/float, never for bool (mirror the panel-4 guard, line 188)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _safe_avg(numerator, denominator):
    """Guarded division (AC-1): "no data" when either operand is non-numeric or denominator <= 0.

    Treats bool as non-numeric for both operands, so True/False never act as 1/0. The guard
    precedes the division, so ZeroDivisionError is never raised.
    """
    if not _is_number(numerator) or not _is_number(denominator) or denominator <= 0:
        return "no data"
    return numerator / denominator


def _share_pct(value, total):
    """Guarded percentage (MAR-4 spec 01): round(value / total * 100, 4), 0-100 scale.

    None on a zero/absent/negative total or a non-numeric value — never a division by zero,
    never a fabricated share. Mirrors _safe_avg's guard-before-divide style.
    """
    if not _is_number(total) or total <= 0 or not _is_number(value):
        return None
    return round(value / total * 100, 4)


def _elapsed_seconds(start_iso, end_iso):
    """Wall-clock elapsed `end - start` in whole seconds, or None (AC-2).

    Thin delegate over acs_lib.elapsed_seconds, the single shared primitive both this
    function and acs_lib.run_seconds adapt (design D1-C) — so a missing/invalid anchor or
    an inverted interval is None, distinguishable from a true zero-length interval, with
    that guarantee enforced in exactly one place. Total function: never raises.

    Overlap-safe guarantee (spec 02 / design B1): an inverted interval (start > end) returns
    None rather than raising or returning a negative value. Callers (_panel7_row) map None to
    the string "no data" and append a meta.degraded entry; aggregate() writes nothing in any
    case. This guarantee covers both the lead-inversion case (merge-pr.ended_at <
    ticket.created_at) and the cycle-inversion case (code.started_at > merge-pr.ended_at, e.g.
    a re-cycled ticket).
    """
    return acs_lib.elapsed_seconds(start_iso, end_iso)


def _parse_due_date(value):
    """Parse a due_date string to a datetime.date, or return None on any failure.

    Accepts YYYY-MM-DD (bare date) or YYYY-MM-DDTHH:MM:SSZ (datetime); returns
    a datetime.date for both.  Returns None for None, non-string, or any parse failure.
    This is module-private: do NOT widen acs_lib.parse_iso (spec 02:71-89, R-B1).
    """
    import datetime
    if not isinstance(value, str) or not value:
        return None
    # Try bare YYYY-MM-DD first (the dominant test and production format).
    try:
        return datetime.date.fromisoformat(value[:10])
    except ValueError:
        pass
    # Try YYYY-MM-DDTHH:MM:SSZ (fall back to extracting the date portion).
    try:
        dt = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
        return dt.date()
    except ValueError:
        return None


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


# ---------------------------------------------------------------------------
# New panel builders (MAR-14 spec 01) — read-only, no writes, stdlib-only
# ---------------------------------------------------------------------------

def _delivery_summary(tickets, prs, panel7, p4_rows, degrade, escalations_by_ticket=None):
    """Compute the delivery_summary panel (5 PM KPIs + additive escalations) from
    already-resolved data.

    Keys (spec 01:92-127):
      tickets_done_over_total  — "<done>/<total>" string; always present.
      prs_merged               — int from prs.merged (or 0 when absent).
      avg_lead_seconds         — float or "no data" from panel7["avg_lead_seconds"].
      avg_cycle_seconds        — float or "no data" from panel7["avg_cycle_seconds"].
      coverage_pass_rate       — "<passed>/<measured>" or "no data"; measured from p4_rows where
                                  cell != "no data"; passed where also passed==True.
      escalations              — additive sub-object (MAR-109 D5), four integer tallies computed
                                  from escalations_by_ticket {ticket_id -> [event, ...]}:
                                    events              — total events across all tickets.
                                    fast_lane_escalated — distinct tickets whose earliest event's
                                                          from_lane is fast (TRIVIAL/SMALL) and whose
                                                          highest-ever to_lane reaches >=STANDARD
                                                          (per-ticket tally, user decision C-1).
                                    deescalations       — events with direction == "down".
                                    silent_reversals    — "down" events with a falsy confirmation_ref.

    meta.degraded entry added only when measured == 0 (coverage_pass_rate unavailable).
    """
    done_count = sum(1 for t in tickets.values()
                     if isinstance(t, dict) and t.get("status") == "done")
    total_count = len(tickets)
    tickets_done_over_total = "%d/%d" % (done_count, total_count)

    prs_merged = prs.get("merged", 0) if isinstance(prs, dict) else 0
    if not isinstance(prs_merged, int) or isinstance(prs_merged, bool):
        prs_merged = 0

    avg_lead_seconds = panel7.get("avg_lead_seconds", "no data")
    avg_cycle_seconds = panel7.get("avg_cycle_seconds", "no data")

    # coverage_pass_rate: count rows where cell != "no data" (measured) and passed==True (passed).
    measured = 0
    passed = 0
    for row in p4_rows:
        if not isinstance(row, dict):
            continue
        cell = row.get("cell")
        if cell == "no data":
            continue  # this row does not contribute to measured
        measured += 1
        if row.get("passed") is True:
            passed += 1

    if measured == 0:
        coverage_pass_rate = "no data"
        degrade(None, "delivery_summary",
                "no coverage data — coverage_pass_rate unavailable")
    else:
        coverage_pass_rate = "%d/%d" % (passed, measured)

    escalations = _escalations_tally(escalations_by_ticket or {})

    return {
        "tickets_done_over_total": tickets_done_over_total,
        "prs_merged": prs_merged,
        "avg_lead_seconds": avg_lead_seconds,
        "avg_cycle_seconds": avg_cycle_seconds,
        "coverage_pass_rate": coverage_pass_rate,
        "escalations": escalations,
    }


def _escalations_tally(escalations_by_ticket):
    """Reduce {ticket_id -> [event, ...]} to the four G25 tallies (MAR-109 D5)."""
    events_total = 0
    fast_lane_escalated = 0
    deescalations = 0
    silent_reversals = 0

    for ticket_events in escalations_by_ticket.values():
        events_total += len(ticket_events)

        origin_rank = None
        highest_rank = None
        for event in ticket_events:
            if not isinstance(event, dict):
                continue
            from_rank = acs_lib.lane_rank(event.get("from_lane"))
            to_rank = acs_lib.lane_rank(event.get("to_lane"))
            if origin_rank is None:
                origin_rank = from_rank
            highest_rank = to_rank if highest_rank is None else max(highest_rank, to_rank)

            if event.get("direction") == "down":
                deescalations += 1
                if not event.get("confirmation_ref"):
                    silent_reversals += 1

        if (origin_rank is not None and origin_rank <= acs_lib.lane_rank("SMALL")
                and highest_rank is not None and highest_rank >= acs_lib.lane_rank("STANDARD")):
            fast_lane_escalated += 1

    return {
        "events": events_total,
        "fast_lane_escalated": fast_lane_escalated,
        "deescalations": deescalations,
        "silent_reversals": silent_reversals,
    }


def _issues_panel(tickets):
    """Build the issues list: one object per ticket, sorted by id (spec 01:129-149).

    Fields per object: id, title, status, type, external_key.
    external_key: index entry external["key"] when external is a dict with a "key"; else None.
    When index is empty, returns [] (never "no data"). No meta.degraded entry.
    """
    result = []
    for ticket_id in sorted(tickets.keys()):
        entry = tickets[ticket_id]
        if not isinstance(entry, dict):
            entry = {}
        external = entry.get("external")
        if isinstance(external, dict) and "key" in external:
            external_key = external["key"]
        else:
            external_key = None
        result.append({
            "id": ticket_id,
            "title": entry.get("title"),
            "status": entry.get("status"),
            "type": entry.get("type"),
            "external_key": external_key,
        })
    return result


def _progress_panel(tickets, merge_ended_at, ticket_updated_at, degrade):
    """Build the progress panel: overall, per_epic, burn_up (spec 01:151-229).

    overall: {"done": <int>, "total": <int>} — always present.
    per_epic: list sorted by epic_id — each entry covers one epic-type ticket.
    burn_up: date-ordered cumulative series, or [] (no done tickets), or "no data" +
             meta.degraded (done tickets exist but no timestamps recoverable for ANY of them).
    """
    # overall
    done_count = sum(1 for t in tickets.values()
                     if isinstance(t, dict) and t.get("status") == "done")
    total_count = len(tickets)
    overall = {"done": done_count, "total": total_count}

    # per_epic: tickets with type == "epic", sorted by epic_id
    per_epic = []
    for epic_id in sorted(k for k, v in tickets.items()
                          if isinstance(v, dict) and v.get("type") == "epic"):
        epic_entry = tickets[epic_id]
        children_ids = epic_entry.get("children") if isinstance(epic_entry, dict) else None
        children_ids = children_ids if isinstance(children_ids, list) else []
        child_done = 0
        child_total = len(children_ids)
        for child_id in children_ids:
            child_entry = tickets.get(child_id)
            if isinstance(child_entry, dict) and child_entry.get("status") == "done":
                child_done += 1
            # Children not found in index are counted in total only (spec 01:186-189)
        per_epic.append({
            "epic_id": epic_id,
            "title": epic_entry.get("title") if isinstance(epic_entry, dict) else None,
            "done": child_done,
            "total": child_total,
        })

    # burn_up: collect (date_str, ticket_id) pairs for done tickets with a recoverable date.
    # Priority: merge-pr.ended_at, then ticket.json.updated_at (spec 01:193-202).
    done_ticket_ids = [tid for tid, t in tickets.items()
                       if isinstance(t, dict) and t.get("status") == "done"]
    if not done_ticket_ids:
        burn_up = []
    else:
        date_pairs = []  # list of (date_str, ticket_id)
        for tid in done_ticket_ids:
            ended = merge_ended_at.get(tid)
            date_str = None
            if ended and acs_lib.parse_iso(ended) is not None:
                date_str = ended[:10]  # ISO date portion YYYY-MM-DD
            else:
                updated = ticket_updated_at.get(tid)
                if updated and acs_lib.parse_iso(updated) is not None:
                    date_str = updated[:10]
            if date_str is not None:
                date_pairs.append((date_str, tid))

        if not date_pairs:
            # All done tickets lack a recoverable date (spec 01:220-224)
            burn_up = "no data"
            degrade(None, "progress",
                    "no completion timestamps recoverable — burn_up unavailable")
        else:
            # Sort by (date, ticket_id) for determinism (spec 01:213-215)
            date_pairs.sort(key=lambda p: (p[0], p[1]))
            # Accumulate cumulative; collapse same-date pairs to the final cumulative (spec 01:216-220)
            cumulative = 0
            by_date = {}  # date_str -> highest cumulative for that date
            for date_str, _tid in date_pairs:
                cumulative += 1
                by_date[date_str] = cumulative
            # Emit one point per unique date in sorted order
            burn_up = [
                {"date": d, "completed_cumulative": by_date[d], "total": total_count}
                for d in sorted(by_date.keys())
            ]

    return {
        "overall": overall,
        "per_epic": per_epic,
        "burn_up": burn_up,
    }


def _deadline_panel(tickets_with_due, now_date, degrade):
    """Build the deadline panel from per-ticket due_date data (MAR-15 spec 02).

    tickets_with_due: list of {id, due_date (str|None), status (str|None)} dicts.
    now_date: datetime.date reference instant (from _parse_due_date(_now_str)); may be None
              if _now_str itself was unparseable (production wall-clock is always parseable).
    degrade: accumulator closure.

    Returns a rows+rollup dict when at least one ticket has a parseable due_date.
    Falls back to the MAR-14 'not set' degraded frame (+ meta.degraded B1 entry) when
    NO ticket has a parseable due_date, or when tickets_with_due is empty.
    """
    _NOT_SET_FRAME = {
        "status": "not set",
        "due_date": None,
        "message": "No due date configured. Set due_date on the ticket.",
    }

    # Empty list -> degrade immediately (no tickets to derive from)
    if not tickets_with_due:
        degrade(None, "deadline",
                "deadline not configured — no tickets in workspace")
        return _NOT_SET_FRAME

    rows = []
    rollup = {"on_track": 0, "overdue": 0, "not_set": 0}
    for entry in tickets_with_due:
        tid = entry.get("id", "")
        raw_due = entry.get("due_date")
        tkt_status = entry.get("status", "")

        parsed = _parse_due_date(raw_due)
        if parsed is None or now_date is None:
            row_status = "not-set"
            rollup["not_set"] += 1
        elif tkt_status == "done":
            # done overrides overdue: a completed ticket is never considered overdue.
            row_status = "on-track"
            rollup["on_track"] += 1
        elif parsed < now_date:
            row_status = "overdue"
            rollup["overdue"] += 1
        else:
            row_status = "on-track"
            rollup["on_track"] += 1

        rows.append({"id": tid, "due_date": raw_due, "status": row_status})

    # If EVERY row is not-set (no parseable due_date anywhere), degrade to the MAR-14 frame.
    if rollup["on_track"] == 0 and rollup["overdue"] == 0:
        degrade(None, "deadline",
                "deadline not configured — no parseable due_date on any ticket")
        return _NOT_SET_FRAME

    return {"rows": rows, "rollup": rollup}


def _usage_summary_panel(totals, prs, panel3_averages, ticket_count):
    """Build the usage_summary panel from already-computed totals and panel3 averages (spec 01:251-269).

    Keys:
      total_cost_usd                  — float from totals.cost_usd (or 0.0).
      total_tokens_input               — int from totals.tokens.input (or 0).
      total_tokens_output              — int from totals.tokens.output (or 0).
      total_runs                       — int from totals.runs (or 0).
      total_working_seconds            — int/float/None from totals.working_seconds (pass-through).
      prs_merged                       — int from prs.merged (or 0).
      avg_working_seconds_per_ticket   — from panel3_averages (float or "no data").
      avg_working_seconds_per_pr       — from panel3_averages (float or "no data").
      avg_cost_per_ticket              — from panel3_averages (float or "no data").
      avg_cost_per_pr                  — from panel3_averages (float or "no data").
      total_api_duration_ms            — float from totals.api_duration_ms (or 0.0, MAR-7).
      avg_api_duration_ms_per_ticket   — total_api_duration_ms / ticket_count (or "no data", MAR-7).
      avg_api_duration_ms_per_pr       — total_api_duration_ms / prs_merged (or "no data", MAR-7).

    No meta.degraded entry (degrades to zeros, never absent).
    """
    t = totals if isinstance(totals, dict) else {}
    tokens = t.get("tokens", {})
    tokens = tokens if isinstance(tokens, dict) else {}

    total_cost_usd = t.get("cost_usd", 0.0)
    if not _is_number(total_cost_usd):
        total_cost_usd = 0.0

    total_tokens_input = tokens.get("input", 0)
    if not isinstance(total_tokens_input, int) or isinstance(total_tokens_input, bool):
        total_tokens_input = 0

    total_tokens_output = tokens.get("output", 0)
    if not isinstance(total_tokens_output, int) or isinstance(total_tokens_output, bool):
        total_tokens_output = 0

    total_runs = t.get("runs", 0)
    if not isinstance(total_runs, int) or isinstance(total_runs, bool):
        total_runs = 0

    # total_working_seconds: pass-through as-is (may be None when absent; spec 01:262)
    total_working_seconds = t.get("working_seconds")

    prs_merged = prs.get("merged", 0) if isinstance(prs, dict) else 0
    if not isinstance(prs_merged, int) or isinstance(prs_merged, bool):
        prs_merged = 0

    avgs = panel3_averages if isinstance(panel3_averages, dict) else {}

    total_api_duration_ms = t.get("api_duration_ms", 0.0)
    if not _is_number(total_api_duration_ms):
        total_api_duration_ms = 0.0

    return {
        "total_cost_usd": total_cost_usd,
        "total_tokens_input": total_tokens_input,
        "total_tokens_output": total_tokens_output,
        "total_runs": total_runs,
        "total_working_seconds": total_working_seconds,
        "prs_merged": prs_merged,
        "avg_working_seconds_per_ticket": avgs.get("avg_working_seconds_per_ticket", "no data"),
        "avg_working_seconds_per_pr": avgs.get("avg_working_seconds_per_pr", "no data"),
        "avg_cost_per_ticket": avgs.get("avg_cost_per_ticket", "no data"),
        "avg_cost_per_pr": avgs.get("avg_cost_per_pr", "no data"),
        "total_api_duration_ms": total_api_duration_ms,
        "avg_api_duration_ms_per_ticket": _safe_avg(total_api_duration_ms, ticket_count),
        "avg_api_duration_ms_per_pr": _safe_avg(total_api_duration_ms, prs_merged),
    }


def _empty_panel6_bucket():
    """Shared panel-6 bucket shape (MAR-4 spec 01): the four token classes plus a running cost.

    Replaces the two independent 3-key literals (the `burn` seed and _accumulate_burn's
    setdefault) that previously had to be kept in lockstep by hand.
    """
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0, "cost": 0.0}


def _apply_panel6_shares(burn):
    """Repo-scope token_share_pct/cost_share_pct on every panel-6 bucket, computed once,
    post-loop (D2 placement; MAR-4 spec 01). Percentage scale is 0-100. Mutates `burn` in place.
    """
    token_total = sum(
        b["input"] + b["output"] + b["cache_creation"] + b["cache_read"] for b in burn.values()
    )
    cost_total = sum(b["cost"] for b in burn.values())
    for bucket in burn.values():
        token_sum = bucket["input"] + bucket["output"] + bucket["cache_creation"] + bucket["cache_read"]
        bucket["token_share_pct"] = _share_pct(token_sum, token_total)
        bucket["cost_share_pct"] = _share_pct(bucket["cost"], cost_total)


def _empty_model_bucket():
    """Raw (pre-finalization) per-model accumulator for usage_by_model (MAR-3 spec 04)."""
    return {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0,
            "cost_sum": 0.0, "cost_seen": False}


def _empty_skill_duration_bucket():
    """Raw (pre-finalization) per-skill duration accumulator for usage_by_ticket.skills[] and
    panel 3's step_api_duration (MAR-7 spec 01). Mirrors _empty_model_bucket's seen/sum-pair
    pattern: a None-elapsed run or a None/non-numeric api_duration_ms is excluded from its own
    sum but never prevents the skill from appearing (never a fabricated 0)."""
    return {"api_duration_ms_sum": 0.0, "api_duration_seen": False,
            "run_seconds_sum": 0.0, "run_seconds_seen": False, "runs": []}


def _fold_model_bucket(dest, src):
    """Add one raw model accumulator's counts into another, in place."""
    dest["input"] += src["input"]
    dest["output"] += src["output"]
    dest["cache_creation"] += src["cache_creation"]
    dest["cache_read"] += src["cache_read"]
    dest["cost_sum"] += src["cost_sum"]
    dest["cost_seen"] = dest["cost_seen"] or src["cost_seen"]


def _finalize_model_bucket(model, bucket):
    """Raw accumulator -> the panel's public item shape (cost roll-up rule, spec 04).

    cost_usd is the sum of non-null contributing costs, never a fabricated 0: None with
    cost_basis "unavailable" when no contributing model_usage item carried a numeric cost,
    else "apportioned" with cost_usd rounded to 6 places (mirrors _accumulate_burn's rounding).
    """
    return {
        "model": model,
        "input": bucket["input"],
        "output": bucket["output"],
        "cache_creation": bucket["cache_creation"],
        "cache_read": bucket["cache_read"],
        "cost_usd": round(bucket["cost_sum"], 6) if bucket["cost_seen"] else None,
        "cost_basis": "apportioned" if bucket["cost_seen"] else "unavailable",
    }


def _usage_by_model_panel(repo_models, ticket_model_rows):
    """Build panels.usage_by_model: repo scope + per-ticket scope (MAR-3 spec 04, AC-2).

    repo_models: {model -> raw accumulator} folded across every ticket/skill.
    ticket_model_rows: [(ticket_id, {model -> raw accumulator}), ...] in ticket iteration order.
    "no data" (repo, or a ticket's own "models") when nothing contributed at that scope --
    e.g. a legacy pre-MAR-3 run entry with no model_usage (AC-6 forward-only gap, disclosed).
    """
    if repo_models:
        repo = [_finalize_model_bucket(m, repo_models[m]) for m in sorted(repo_models)]
    else:
        repo = "no data"

    tickets = []
    for ticket_id, models in ticket_model_rows:
        if models:
            models_list = [_finalize_model_bucket(m, models[m]) for m in sorted(models)]
        else:
            models_list = "no data"
        tickets.append({"ticket_id": ticket_id, "models": models_list})

    return {"repo": repo, "tickets": tickets}


def _finalize_role_ticket_bucket(bucket, token_total, cost_total):
    """Raw per-role accumulator -> usage_by_ticket's public role-item shape (MAR-4 spec 01).

    cost_usd/cost_basis follow the model roll-up rule (None/"unavailable" when this role had no
    measured cost in this ticket, independent of sibling roles in the same ticket). Both
    percentages are ticket-scoped (token_total/cost_total are this ticket's own sums, never the
    repo total). cost_share_pct is None whenever cost_usd is None OR the ticket-scope cost total
    is zero/absent (a role with no measured cost cannot express a share of an unknown quantity).
    """
    token_sum = bucket["input"] + bucket["output"] + bucket["cache_creation"] + bucket["cache_read"]
    cost_usd = round(bucket["cost_sum"], 6) if bucket["cost_seen"] else None
    return {
        "input": bucket["input"],
        "output": bucket["output"],
        "cache_creation": bucket["cache_creation"],
        "cache_read": bucket["cache_read"],
        "cost_usd": cost_usd,
        "cost_basis": "apportioned" if bucket["cost_seen"] else "unavailable",
        "token_share_pct": _share_pct(token_sum, token_total),
        "cost_share_pct": _share_pct(cost_usd, cost_total) if cost_usd is not None else None,
    }


def _finalize_skill_bucket(skill, bucket):
    """Raw per-skill duration accumulator -> usage_by_ticket.skills[]'s public item shape
    (MAR-7 spec 01). Structural mirror of _finalize_model_bucket's cost roll-up rule: a rolled-up
    figure across possibly several run entries collapses to "apportioned"/"unavailable" (never a
    fabricated 0) -- distinct from _panel3_row's step_api_duration cell, which passes through a
    single contributing run's own literal basis rather than collapsing it.
    """
    return {
        "skill": skill,
        "run_seconds_sum": round(bucket["run_seconds_sum"], 4) if bucket["run_seconds_seen"] else None,
        "api_duration_ms": round(bucket["api_duration_ms_sum"], 4) if bucket["api_duration_seen"] else None,
        "api_duration_basis": "apportioned" if bucket["api_duration_seen"] else "unavailable",
        "runs": bucket["runs"],
    }


def _usage_by_ticket_panel(ticket_role_rows, ticket_skill_rows):
    """Build panels.usage_by_ticket: ticket-scoped role-share percentages (MAR-4 spec 01, AC-1),
    widened with ticket-scope api_duration_ms/api_duration_basis and a skills[] array (MAR-7
    spec 01, D5.4/S-C).

    ticket_role_rows: [(ticket_id, {role -> raw accumulator}), ...] in ticket iteration order.
    ticket_skill_rows: [(ticket_id, {skill -> raw duration accumulator}), ...], same order.
    A ticket's "roles" is the literal "no data" when it contributed no role_usage anywhere;
    otherwise a dict keyed by role name (no repeated "role" key inside each bucket), inserted in
    sorted() role-name order for determinism -- the renderer never re-sorts (D2 placement).
    api_duration_ms/api_duration_basis are ticket-scope siblings of "roles", folded across this
    ticket's own ticket_skills raw buckets (identical roll-up discipline to the skill-level
    figure, never double-derived from skills[]'s own already-rounded sums). "skills" is an EMPTY
    list -- never the string "no data" -- when the ticket has run entries but none carries a
    measured/apportioned duration; that distinguishes "no data at all" from "measured, all
    unavailable" (Risk 3 / test 8).
    """
    skill_map = dict(ticket_skill_rows)
    tickets = []
    for ticket_id, roles_raw in ticket_role_rows:
        if not roles_raw:
            roles = "no data"
        else:
            token_total = sum(
                b["input"] + b["output"] + b["cache_creation"] + b["cache_read"]
                for b in roles_raw.values()
            )
            cost_total = sum(b["cost_sum"] for b in roles_raw.values())
            roles = {
                role: _finalize_role_ticket_bucket(roles_raw[role], token_total, cost_total)
                for role in sorted(roles_raw)
            }

        ticket_skills = skill_map.get(ticket_id) or {}
        api_ms_sum = 0.0
        api_seen = False
        for bucket in ticket_skills.values():
            if bucket["api_duration_seen"]:
                api_ms_sum += bucket["api_duration_ms_sum"]
                api_seen = True

        # A skill row is emitted only when at least one of its runs actually measured/apportioned
        # a duration -- a skill with run entries but api_duration_seen==False everywhere is
        # excluded (never a content-free row), which is what makes an all-"unavailable" ticket's
        # skills == [] rather than a row of null-duration noise (Risk 3 / test 8).
        skills = [
            _finalize_skill_bucket(skill, ticket_skills[skill])
            for skill in acs_lib.HOOKED_SKILLS
            if skill in ticket_skills and ticket_skills[skill]["api_duration_seen"]
        ]

        tickets.append({
            "ticket_id": ticket_id,
            "roles": roles,
            "api_duration_ms": round(api_ms_sum, 4) if api_seen else None,
            "api_duration_basis": "apportioned" if api_seen else "unavailable",
            "skills": skills,
        })
    return {"tickets": tickets}


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


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    """Thin smoke path: resolve {workspace, repo_id} via build_context, aggregate, print JSON."""
    ctx = acs_lib.build_context(os.getcwd())
    result = aggregate(ctx["workspace"], ctx["repo_id"])
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
