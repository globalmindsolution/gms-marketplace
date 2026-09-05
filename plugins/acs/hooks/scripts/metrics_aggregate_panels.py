"""metrics_aggregate_panels — the five MAR-14 spec-02 panel builders
(extracted from metrics_aggregate.py by MAR-531).

delivery_summary, issues, progress, deadline and usage_summary: each folds the
already-loaded ticket rows into one panel value. None of them reads the disk.
"""


import acs_lib  # noqa: E402

from metrics_aggregate_common import _is_number, _parse_due_date, _safe_avg



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
