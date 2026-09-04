"""metrics_render_panels — the five MAR-14 spec-02 panels, both surfaces
(extracted from metrics_render.py by MAR-531).

delivery_summary, issues, progress, deadline and usage_summary each have a
terminal and an HTML renderer; they live together because the pair is one
decision about how that panel reads, not two.
"""


import argparse
import html as _html
import json
import os
import sys
import acs_lib  # noqa: E402

from metrics_render_common import NO_DATA, _bar, _bar_pct, _esc, _fmt_money, _html_bar_cell, _humanize_ms, _humanize_seconds, _is_no_data
from metrics_render_terminal import _term_no_data_block
from metrics_render_html import _html_no_data



# ---------------------------------------------------------------------------
# MAR-14 spec 02 — New per-panel renderers for the five spec-01 keys
# All values from panel dicts pass through _esc() before emission (NFR Security).
# No new imports; no clock reads; all helpers reused from above.
# ---------------------------------------------------------------------------

def _term_render_delivery_summary(panel):
    """Terminal renderer for the delivery_summary panel (spec 02 §_render_delivery_summary_terminal).

    Renders 5 KPIs + the additive escalations sub-object (MAR-109 D5) in fixed order.
    'no data' string or non-dict -> single 'no data' row (B1).
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _term_no_data_block()
    out = []
    tickets_done = panel.get("tickets_done_over_total", NO_DATA)
    out.append("  tickets done/total:  %s" % _esc(str(tickets_done)))
    prs_merged = panel.get("prs_merged", NO_DATA)
    out.append("  PRs merged:          %s" % _esc(str(prs_merged)))
    avg_lead = panel.get("avg_lead_seconds", NO_DATA)
    out.append("  avg lead time:       %s" % (_humanize_seconds(avg_lead) if not _is_no_data(avg_lead)
                                               else NO_DATA))
    avg_cycle = panel.get("avg_cycle_seconds", NO_DATA)
    out.append("  avg cycle time:      %s" % (_humanize_seconds(avg_cycle) if not _is_no_data(avg_cycle)
                                               else NO_DATA))
    cov = panel.get("coverage_pass_rate", NO_DATA)
    out.append("  coverage pass rate:  %s" % _esc(str(cov)))
    esc = panel.get("escalations") if isinstance(panel.get("escalations"), dict) else {}
    out.append("  escalation events:          %s" % _esc(str(esc.get("events", 0))))
    out.append("  fast-lane escalated:        %s" % _esc(str(esc.get("fast_lane_escalated", 0))))
    out.append("  deescalations:              %s" % _esc(str(esc.get("deescalations", 0))))
    out.append("  silent reversals:           %s" % _esc(str(esc.get("silent_reversals", 0))))
    return out


def _html_render_delivery_summary(panel):
    """HTML renderer for the delivery_summary panel (spec 02 §_render_delivery_summary_html).

    Self-contained table with 5 KPI rows + the additive escalations sub-object (MAR-109 D5).
    'no data' string or non-dict -> nodata div (B1).
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _html_no_data()
    rows = ["<tr><th>KPI</th><th>value</th></tr>"]
    tickets_done = panel.get("tickets_done_over_total", NO_DATA)
    rows.append("<tr><td>tickets done/total</td><td>%s</td></tr>" % _esc(str(tickets_done)))
    prs_merged = panel.get("prs_merged", NO_DATA)
    rows.append("<tr><td>PRs merged</td><td>%s</td></tr>" % _esc(str(prs_merged)))
    avg_lead = panel.get("avg_lead_seconds", NO_DATA)
    lead_str = _humanize_seconds(avg_lead) if not _is_no_data(avg_lead) else NO_DATA
    cls = ' class="nodata"' if lead_str == NO_DATA else ""
    rows.append("<tr><td>avg lead time</td><td%s>%s</td></tr>" % (cls, _esc(lead_str)))
    avg_cycle = panel.get("avg_cycle_seconds", NO_DATA)
    cycle_str = _humanize_seconds(avg_cycle) if not _is_no_data(avg_cycle) else NO_DATA
    cls = ' class="nodata"' if cycle_str == NO_DATA else ""
    rows.append("<tr><td>avg cycle time</td><td%s>%s</td></tr>" % (cls, _esc(cycle_str)))
    cov = panel.get("coverage_pass_rate", NO_DATA)
    rows.append("<tr><td>coverage pass rate</td><td>%s</td></tr>" % _esc(str(cov)))
    esc = panel.get("escalations") if isinstance(panel.get("escalations"), dict) else {}
    rows.append("<tr><td>escalation events</td><td>%s</td></tr>" % _esc(str(esc.get("events", 0))))
    rows.append("<tr><td>fast-lane escalated</td><td>%s</td></tr>"
                % _esc(str(esc.get("fast_lane_escalated", 0))))
    rows.append("<tr><td>deescalations</td><td>%s</td></tr>" % _esc(str(esc.get("deescalations", 0))))
    rows.append("<tr><td>silent reversals</td><td>%s</td></tr>"
                % _esc(str(esc.get("silent_reversals", 0))))
    return "<table>" + "".join(rows) + "</table>"


def _term_render_issues(panel):
    """Terminal renderer for the issues panel (spec 02 §_render_issues_terminal).

    'no data' -> single 'no data' row. [] -> 'no issues' placeholder. Non-empty list -> one
    line per issue (id, title, status, type, external_key). Preserves list order (spec 01 sorts
    ascending by id; do NOT re-sort here — fixed order already guaranteed).
    """
    if _is_no_data(panel) or not isinstance(panel, list):
        return _term_no_data_block()
    if not panel:
        return ["  no issues"]
    out = ["  %-12s  %-24s  %-12s  %-10s  %s" % ("id", "title", "status", "type", "external_key")]
    for issue in panel:
        if not isinstance(issue, dict):
            continue
        ext = _esc(issue["external_key"]) if issue.get("external_key") is not None else ""
        out.append("  %-12s  %-24s  %-12s  %-10s  %s"
                   % (_esc(issue.get("id", "")),
                      _esc(issue.get("title") or ""),
                      _esc(issue.get("status") or ""),
                      _esc(issue.get("type") or ""),
                      ext))
    return out


def _html_render_issues(panel):
    """HTML renderer for the issues panel (spec 02 §_render_issues_html).

    'no data' -> nodata div. [] -> 'no issues' row. Non-empty list -> HTML table one row per issue.
    """
    if _is_no_data(panel) or not isinstance(panel, list):
        return _html_no_data()
    if not panel:
        return '<div class="nodata">no issues</div>'
    rows = ["<tr><th>id</th><th>title</th><th>status</th><th>type</th><th>external_key</th></tr>"]
    for issue in panel:
        if not isinstance(issue, dict):
            continue
        ext = _esc(issue["external_key"]) if issue.get("external_key") is not None else ""
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (_esc(issue.get("id", "")),
                       _esc(issue.get("title") or ""),
                       _esc(issue.get("status") or ""),
                       _esc(issue.get("type") or ""),
                       ext))
    return "<table>" + "".join(rows) + "</table>"


def _term_render_progress(panel):
    """Terminal renderer for the progress panel (spec 02 §_render_progress_terminal).

    Three sub-sections: overall done/total bar; per-epic breakdown; burn-up series.
    'no data' or non-dict -> single 'no data' row (B1).
    burn_up == 'no data' -> degraded note (B1 — section still rendered).
    burn_up == [] -> 'no completed tickets' placeholder.
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _term_no_data_block()
    out = []
    # Overall
    overall = panel.get("overall") if isinstance(panel.get("overall"), dict) else {}
    done = overall.get("done", 0)
    total = overall.get("total", 0)
    bar = _bar(done, total) if total > 0 else _bar(0, 1)
    out.append("  overall: %s/%s  %s" % (done, total, bar))
    # Per-epic (list order is already sorted by spec 01; do NOT re-sort)
    per_epic = panel.get("per_epic") if isinstance(panel.get("per_epic"), list) else []
    if not per_epic:
        out.append("  epics: no epics")
    else:
        out.append("  epics:")
        for e in per_epic:
            if not isinstance(e, dict):
                continue
            ebar = _bar(e.get("done", 0), e.get("total", 1) or 1)
            out.append("    %-16s %-24s  %s/%s  %s"
                       % (_esc(e.get("epic_id", "")),
                          _esc(e.get("title") or ""),
                          e.get("done", 0), e.get("total", 0), ebar))
    # Burn-up
    burn_up = panel.get("burn_up")
    if _is_no_data(burn_up):
        out.append("  burn-up: " + NO_DATA + " (no completion timestamps recoverable)")
    elif isinstance(burn_up, list) and not burn_up:
        out.append("  burn-up: no completed tickets")
    elif isinstance(burn_up, list):
        out.append("  burn-up:")
        out.append("    %-12s  %6s  %5s" % ("date", "done", "total"))
        for point in burn_up:
            if not isinstance(point, dict):
                continue
            out.append("    %-12s  %6s  %5s"
                       % (_esc(str(point.get("date", ""))),
                          point.get("completed_cumulative", 0),
                          point.get("total", 0)))
    else:
        out.append("  burn-up: " + NO_DATA)
    return out


def _html_render_progress(panel):
    """HTML renderer for the progress panel (spec 02 §_render_progress_html).

    Three sub-sections in a single panel div: overall, per-epic table, burn-up table.
    'no data' or non-dict -> nodata div (B1).
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _html_no_data()
    parts = []
    # Overall
    overall = panel.get("overall") if isinstance(panel.get("overall"), dict) else {}
    done = overall.get("done", 0)
    total = overall.get("total", 0)
    pct = _bar_pct(done, total)
    parts.append("<p>Overall: %s/%s %s</p>"
                 % (_esc(str(done)), _esc(str(total)),
                    '<span class="acs-bar-track"><span class="acs-bar" style="width:%d%%"></span></span>' % pct))
    # Per-epic
    per_epic = panel.get("per_epic") if isinstance(panel.get("per_epic"), list) else []
    if not per_epic:
        parts.append('<p class="nodata">no epics</p>')
    else:
        rows = ["<tr><th>epic</th><th>title</th><th>done</th><th>total</th><th>bar</th></tr>"]
        for e in per_epic:
            if not isinstance(e, dict):
                continue
            epct = _bar_pct(e.get("done", 0), e.get("total", 1) or 1)
            rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                        % (_esc(e.get("epic_id", "")),
                           _esc(e.get("title") or ""),
                           _esc(str(e.get("done", 0))),
                           _esc(str(e.get("total", 0))),
                           _html_bar_cell(e.get("done", 0), e.get("total", 1) or 1)))
        parts.append("<table>" + "".join(rows) + "</table>")
    # Burn-up
    burn_up = panel.get("burn_up")
    if _is_no_data(burn_up):
        parts.append('<p class="nodata">burn-up: %s (no completion timestamps recoverable)</p>' % NO_DATA)
    elif isinstance(burn_up, list) and not burn_up:
        parts.append('<p class="nodata">burn-up: no completed tickets</p>')
    elif isinstance(burn_up, list):
        rows = ["<tr><th>date</th><th>completed (cumulative)</th><th>total</th></tr>"]
        for point in burn_up:
            if not isinstance(point, dict):
                continue
            rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                        % (_esc(str(point.get("date", ""))),
                           _esc(str(point.get("completed_cumulative", 0))),
                           _esc(str(point.get("total", 0)))))
        parts.append("<table>" + "".join(rows) + "</table>")
    else:
        parts.append('<p class="nodata">burn-up: %s</p>' % NO_DATA)
    return "".join(parts)


def _term_render_deadline(panel):
    """Terminal renderer for the deadline panel (MAR-15 spec 02).

    Three branches (B1: all present):
    - 'no data' or non-dict -> single 'no data' block.
    - dict with 'rows' key -> per-ticket table + roll-up (real data, MAR-15).
    - dict without 'rows' key -> degraded 'not set' frame (MAR-14 shape, backward-compat).

    Every cell passes through _esc (NFR Security, design.md:101).
    Reads no clock — determinism is preserved by construction (AC-6).
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _term_no_data_block()

    if "rows" in panel:
        # Real data: per-ticket table + roll-up (spec 02 §Renderer changes).
        out = []
        rows = panel.get("rows") or []
        if not rows:
            out.append("  (no tickets)")
        else:
            out.append("  %-20s  %-12s  %s" % ("ticket", "due date", "status"))
            out.append("  " + "-" * 50)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                tid = _esc(str(row.get("id", "")))
                due = row.get("due_date")
                due_str = _esc("—" if due is None else str(due))
                st = _esc(str(row.get("status", "")))
                out.append("  %-20s  %-12s  %s" % (tid, due_str, st))
        rollup = panel.get("rollup") or {}
        out.append("  overdue: %s / on-track: %s / not-set: %s" % (
            _esc(str(rollup.get("overdue", 0))),
            _esc(str(rollup.get("on_track", 0))),
            _esc(str(rollup.get("not_set", 0))),
        ))
        return out

    # Degraded 'not set' frame (MAR-14 shape, backward-compatible).
    out = []
    out.append("  status:   %s" % _esc(str(panel.get("status", ""))))
    due = panel.get("due_date")
    out.append("  due date: %s" % ("—" if due is None else _esc(str(due))))
    out.append("  message:  %s" % _esc(str(panel.get("message", ""))))
    return out


def _html_render_deadline(panel):
    """HTML renderer for the deadline panel (MAR-15 spec 02).

    Three branches (B1: all present):
    - 'no data' or non-dict -> nodata div.
    - dict with 'rows' key -> per-ticket HTML table + roll-up row (real data, MAR-15).
    - dict without 'rows' key -> degraded 'not set' frame table (MAR-14 shape, backward-compat).

    Every cell passes through _esc (NFR Security, design.md:101).
    Reads no clock — determinism is preserved by construction (AC-6).
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _html_no_data()

    if "rows" in panel:
        # Real data: per-ticket table + roll-up (spec 02 §Renderer changes).
        parts = []
        ticket_rows = panel.get("rows") or []
        header = "<tr><th>ticket</th><th>due date</th><th>status</th></tr>"
        trs = [header]
        for row in ticket_rows:
            if not isinstance(row, dict):
                continue
            tid = _esc(str(row.get("id", "")))
            due = row.get("due_date")
            due_str = _esc("—" if due is None else str(due))
            st = _esc(str(row.get("status", "")))
            trs.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (tid, due_str, st))
        parts.append("<table>" + "".join(trs) + "</table>")
        rollup = panel.get("rollup") or {}
        parts.append(
            "<p>overdue: %s / on-track: %s / not-set: %s</p>" % (
                _esc(str(rollup.get("overdue", 0))),
                _esc(str(rollup.get("on_track", 0))),
                _esc(str(rollup.get("not_set", 0))),
            )
        )
        return "".join(parts)

    # Degraded 'not set' frame (MAR-14 shape, backward-compatible).
    due = panel.get("due_date")
    due_str = "—" if due is None else _esc(str(due))
    rows = [
        "<tr><th>field</th><th>value</th></tr>",
        "<tr><td>status</td><td>%s</td></tr>" % _esc(str(panel.get("status", ""))),
        "<tr><td>due date</td><td>%s</td></tr>" % due_str,
        "<tr><td>message</td><td>%s</td></tr>" % _esc(str(panel.get("message", ""))),
    ]
    return "<table>" + "".join(rows) + "</table>"


def _term_render_usage_summary(panel):
    """Terminal renderer for the usage_summary panel (spec 02 §_render_usage_summary_terminal).

    10 KPIs in fixed order. 'no data' or non-dict -> single 'no data' row (B1).
    Duration values -> _humanize_seconds; None total_working_seconds -> 'no data'.
    Cost values -> _fmt_money (2dp); 'no data' averages -> 'no data'.
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _term_no_data_block()
    out = []
    out.append("  total cost (USD):                   %s" % _fmt_money(panel.get("total_cost_usd", 0)))
    out.append("  total tokens input:                 %s" % panel.get("total_tokens_input", 0))
    out.append("  total tokens output:                %s" % panel.get("total_tokens_output", 0))
    out.append("  total runs:                         %s" % panel.get("total_runs", 0))
    ws = panel.get("total_working_seconds")
    ws_str = _humanize_seconds(ws) if ws is not None else NO_DATA
    out.append("  total working time:                 %s" % ws_str)
    out.append("  PRs merged:                         %s" % panel.get("prs_merged", 0))
    avg_wt = panel.get("avg_working_seconds_per_ticket", NO_DATA)
    out.append("  avg working time / ticket:          %s" % (
        _humanize_seconds(avg_wt) if not _is_no_data(avg_wt) else NO_DATA))
    avg_wp = panel.get("avg_working_seconds_per_pr", NO_DATA)
    out.append("  avg working time / merged PR:       %s" % (
        _humanize_seconds(avg_wp) if not _is_no_data(avg_wp) else NO_DATA))
    avg_ct = panel.get("avg_cost_per_ticket", NO_DATA)
    out.append("  avg cost / ticket (USD):            %s" % (
        _fmt_money(avg_ct) if not _is_no_data(avg_ct) else NO_DATA))
    avg_cp = panel.get("avg_cost_per_pr", NO_DATA)
    out.append("  avg cost / merged PR (USD):         %s" % (
        _fmt_money(avg_cp) if not _is_no_data(avg_cp) else NO_DATA))
    # 3 API-duration rows (MAR-7 spec 02) — total row guarded is-not-None like
    # total_working_seconds; the two averages follow the existing NO_DATA-guarded pattern.
    tad = panel.get("total_api_duration_ms")
    out.append("  total API duration:                 %s" % (
        _humanize_ms(tad) if tad is not None else NO_DATA))
    avg_at = panel.get("avg_api_duration_ms_per_ticket", NO_DATA)
    out.append("  avg API duration / ticket:          %s" % (
        _humanize_ms(avg_at) if not _is_no_data(avg_at) else NO_DATA))
    avg_ap = panel.get("avg_api_duration_ms_per_pr", NO_DATA)
    out.append("  avg API duration / merged PR:       %s" % (
        _humanize_ms(avg_ap) if not _is_no_data(avg_ap) else NO_DATA))
    return out


def _html_render_usage_summary(panel):
    """HTML renderer for the usage_summary panel (spec 02 §_render_usage_summary_html).

    10-row KPI table. 'no data' or non-dict -> nodata div (B1).
    """
    if _is_no_data(panel) or not isinstance(panel, dict):
        return _html_no_data()
    rows = ["<tr><th>metric</th><th>value</th></tr>"]
    rows.append("<tr><td>total cost (USD)</td><td>%s</td></tr>"
                % _esc(_fmt_money(panel.get("total_cost_usd", 0))))
    rows.append("<tr><td>total tokens input</td><td>%s</td></tr>"
                % _esc(str(panel.get("total_tokens_input", 0))))
    rows.append("<tr><td>total tokens output</td><td>%s</td></tr>"
                % _esc(str(panel.get("total_tokens_output", 0))))
    rows.append("<tr><td>total runs</td><td>%s</td></tr>"
                % _esc(str(panel.get("total_runs", 0))))
    ws = panel.get("total_working_seconds")
    ws_str = _humanize_seconds(ws) if ws is not None else NO_DATA
    cls = ' class="nodata"' if ws_str == NO_DATA else ""
    rows.append("<tr><td>total working time</td><td%s>%s</td></tr>" % (cls, _esc(ws_str)))
    rows.append("<tr><td>PRs merged</td><td>%s</td></tr>"
                % _esc(str(panel.get("prs_merged", 0))))

    def _avg_row(label, value, fmt):
        v_str = fmt(value) if not _is_no_data(value) else NO_DATA
        c = ' class="nodata"' if v_str == NO_DATA else ""
        return "<tr><td>%s</td><td%s>%s</td></tr>" % (_esc(label), c, _esc(v_str))

    rows.append(_avg_row("avg working time / ticket",
                         panel.get("avg_working_seconds_per_ticket", NO_DATA),
                         _humanize_seconds))
    rows.append(_avg_row("avg working time / merged PR",
                         panel.get("avg_working_seconds_per_pr", NO_DATA),
                         _humanize_seconds))
    rows.append(_avg_row("avg cost / ticket (USD)",
                         panel.get("avg_cost_per_ticket", NO_DATA),
                         _fmt_money))
    rows.append(_avg_row("avg cost / merged PR (USD)",
                         panel.get("avg_cost_per_pr", NO_DATA),
                         _fmt_money))
    # 3 API-duration rows (MAR-7 spec 02) — mirrors the same guard pattern as above.
    tad = panel.get("total_api_duration_ms")
    tad_str = _humanize_ms(tad) if tad is not None else NO_DATA
    cls = ' class="nodata"' if tad_str == NO_DATA else ""
    rows.append("<tr><td>total API duration</td><td%s>%s</td></tr>" % (cls, _esc(tad_str)))
    rows.append(_avg_row("avg API duration / ticket",
                         panel.get("avg_api_duration_ms_per_ticket", NO_DATA),
                         _humanize_ms))
    rows.append(_avg_row("avg API duration / merged PR",
                         panel.get("avg_api_duration_ms_per_pr", NO_DATA),
                         _humanize_ms))
    return "<table>" + "".join(rows) + "</table>"
