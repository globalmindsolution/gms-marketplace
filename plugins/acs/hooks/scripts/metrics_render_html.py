"""metrics_render_html — the self-contained HTML surface
(extracted from metrics_render.py by MAR-531).

ONE string, inline CSS, no external fetch -- the widget host receives it
verbatim. Every value from a panel dict passes through _esc().
"""


import argparse
import html as _html
import json
import os
import sys
import acs_lib  # noqa: E402

from metrics_render_common import NO_DATA, PANEL_KEYS, PANEL_TITLES, ROLE_ORDER, UNAVAILABLE, _average_cells, _counts_items, _esc, _fmt_money, _fmt_pct, _html_bar_cell, _humanize_ms, _humanize_seconds, _is_no_data, _meta_lines, _panel6_extra_roles, _panel_max



# ---------------------------------------------------------------------------
# HTML surface (--html) — ONE self-contained string, inline CSS, NO external fetch
# ---------------------------------------------------------------------------

# Self-contained, theme-adaptive inline style (C-8). Default colors are LIGHT; an
# @media (prefers-color-scheme: dark) block inside the SAME <style> element overrides
# text/surfaces/borders/bars to dark-appropriate tones so the standalone dashboard is
# readable in BOTH light and dark — no host CSS-variable dependency, no external fetch.
# .acs-bar is a deterministic CSS bar: a fixed-width track holding a fill whose
# width:N% is computed (integer percent) from the panel data by _bar_pct.
_HTML_STYLE = (
    "<style>"
    # --- light defaults ---
    ".acs-metrics{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;"
    "line-height:1.4;color:#1a1a1a}"
    ".acs-metrics h2{font-size:15px;margin:0 0 4px}"
    ".acs-metrics .panel{border:1px solid #ccc;border-radius:6px;padding:10px 12px;margin:8px 0}"
    ".acs-metrics .panel h3{font-size:13px;margin:0 0 6px}"
    ".acs-metrics table{border-collapse:collapse;width:100%}"
    ".acs-metrics th,.acs-metrics td{text-align:left;padding:2px 8px 2px 0;"
    "border-bottom:1px solid #eee}"
    ".acs-metrics .meta{color:#555;font-size:12px}"
    ".acs-metrics .nodata{color:#999;font-style:italic}"
    ".acs-metrics .acs-bar-track{display:inline-block;width:120px;height:9px;"
    "background:#e9edf2;border-radius:3px;overflow:hidden;vertical-align:middle}"
    ".acs-metrics .acs-bar{display:block;height:9px;background:#3b6ea5;border-radius:3px}"
    # --- dark overrides (same <style>, no host variable) ---
    "@media (prefers-color-scheme: dark){"
    ".acs-metrics{color:#e6e6e6}"
    ".acs-metrics .panel{border-color:#3a3f46}"
    ".acs-metrics th,.acs-metrics td{border-bottom-color:#2b2f35}"
    ".acs-metrics .meta{color:#a8b0ba}"
    ".acs-metrics .nodata{color:#7c828b}"
    ".acs-metrics .acs-bar-track{background:#2b2f35}"
    ".acs-metrics .acs-bar{background:#5a93d6}"
    "}"
    "</style>"
)


def render_html(data):
    """ONE self-contained HTML string rendering the SAME seven panels. Inline CSS, no fetch. Never raises."""
    data = data if isinstance(data, dict) else {}
    panels = data.get("panels") if isinstance(data.get("panels"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}

    parts = ['<div class="acs-metrics">']
    parts.append(_HTML_STYLE)
    parts.append("<h2>/acs:metrics dashboard</h2>")
    parts.append('<div class="meta">')
    parts.append(" &middot; ".join(_esc(ml) for ml in _meta_lines(meta)))
    parts.append("</div>")

    for key in PANEL_KEYS:
        value = panels.get(key, NO_DATA)
        parts.append('<div class="panel">')
        parts.append("<h3>%s</h3>" % _esc(PANEL_TITLES[key]))
        parts.append(_HTML_PANELS[key](value))
        parts.append("</div>")

    parts.append(_html_degraded(meta.get("degraded")))
    parts.append("</div>")
    return "".join(parts)


def _html_no_data():
    return '<div class="nodata">%s</div>' % NO_DATA


def _html_counts_table(caption, items, panel_max):
    """A counts table with a deterministic theme-adaptive bar column (width:N% of panel_max)."""
    rows = ["<tr><th>%s</th><th>count</th><th>bar</th></tr>" % _esc(caption)]
    if not items:
        rows.append('<tr><td colspan="3" class="nodata">%s</td></tr>' % NO_DATA)
    for label, count in items:
        rows.append("<tr><td>%s</td><td>%s</td>%s</tr>"
                    % (_esc(label), _esc(count), _html_bar_cell(count, panel_max)))
    return "<table>" + "".join(rows) + "</table>"


def _html_panel1(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    status_items = _counts_items(value.get("by_status"))
    type_items = _counts_items(value.get("by_type"))
    # Shared panel_max across status+type so the bars are comparable within the panel
    # (matches the terminal surface's combined peak).
    panel_max = _panel_max([c for _, c in status_items + type_items])
    return (_html_counts_table("status", status_items, panel_max)
            + _html_counts_table("type", type_items, panel_max))


def _html_panel2(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    steps = value.get("steps") if isinstance(value.get("steps"), dict) else {}
    counts = [steps.get(skill, 0) for skill in acs_lib.HOOKED_SKILLS]
    panel_max = _panel_max(counts)
    rows = ["<tr><th>step</th><th>tickets</th><th>bar</th></tr>"]
    for skill in acs_lib.HOOKED_SKILLS:
        count = steps.get(skill, 0)
        rows.append("<tr><td>%s</td><td>%s</td>%s</tr>"
                    % (_esc(skill), _esc(count), _html_bar_cell(count, panel_max)))
    prs = value.get("prs") if isinstance(value.get("prs"), dict) else {}
    rows.append('<tr><td>PRs created</td><td>%s</td><td></td></tr>' % _esc(prs.get("created", 0)))
    rows.append('<tr><td>PRs merged</td><td>%s</td><td></td></tr>' % _esc(prs.get("merged", 0)))
    return "<table>" + "".join(rows) + "</table>"


def _html_panel3_sub_rows(row):
    """HTML equivalent of _term_panel3_sub_rows (MAR-7 spec 02) — one extra <tr> per skill,
    reusing the main row's 3-column shape (skill / step span / API duration + basis)."""
    step_order = row.get("step_order")
    if not isinstance(step_order, list):
        return []
    steps = row.get("steps") if isinstance(row.get("steps"), dict) else {}
    step_api_duration = row.get("step_api_duration") if isinstance(row.get("step_api_duration"), dict) else {}
    out = []
    for skill in step_order:
        step_span = _humanize_seconds(steps.get(skill))
        entry = step_api_duration.get(skill)
        if not isinstance(entry, dict):
            api_str = UNAVAILABLE
        elif entry.get("basis") == "unavailable":
            api_str = UNAVAILABLE
        else:
            api_str = "%s (%s)" % (_humanize_ms(entry.get("ms")), entry.get("basis"))
        out.append("<tr><td>&nbsp;&nbsp;%s</td><td>step span %s</td><td>api duration %s</td></tr>"
                   % (_esc(skill), _esc(step_span), _esc(api_str)))
    return out


def _html_panel3(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    rows = ["<tr><th>ticket</th><th>working time</th><th>cost_usd</th></tr>"]
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        rows.append('<tr><td colspan="3" class="nodata">%s</td></tr>' % NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        totals = row.get("totals") if isinstance(row.get("totals"), dict) else {}
        # C-6: humanize the working time; a missing/non-numeric value still renders the existing
        # no-data text via _humanize_seconds (returns NO_DATA for any non-number — B1 preserved).
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (_esc(row.get("ticket_id", "?")),
                       _esc(_humanize_seconds(totals.get("working_seconds", "-"))),
                       _esc(_fmt_money(totals.get("cost_usd", "-"), empty="-"))))
        rows.extend(_html_panel3_sub_rows(row))
    repo_totals = value.get("repo_totals") if isinstance(value.get("repo_totals"), dict) else {}
    if repo_totals:
        rows.append("<tr><td>REPO TOTAL</td><td>%s</td><td>%s</td></tr>"
                    % (_esc(_humanize_seconds(repo_totals.get("working_seconds", "-"))),
                       _esc(_fmt_money(repo_totals.get("cost_usd", "-"), empty="-"))))
    # Four averages summary rows (B1 — a "no data" average renders the nodata cell, never omitted).
    for label, formatted in _average_cells(value):
        cls = ' class="nodata"' if formatted == NO_DATA else ""
        rows.append('<tr><td>%s</td><td colspan="2"%s>%s</td></tr>'
                    % (_esc(label), cls, _esc(formatted)))
    return "<table>" + "".join(rows) + "</table>"


def _html_panel4(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    rows = ["<tr><th>ticket</th><th>achieved</th><th>target</th><th>passed</th></tr>"]
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        rows.append('<tr><td colspan="4" class="nodata">%s</td></tr>' % NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        tid = _esc(row.get("ticket_id", "?"))
        if row.get("cell") == NO_DATA or "achieved" not in row:
            rows.append('<tr><td>%s</td><td colspan="3" class="nodata">%s</td></tr>' % (tid, NO_DATA))
            continue
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (tid, _esc(row.get("achieved")), _esc(row.get("target")),
                       "yes" if row.get("passed") else "no"))
    return "<table>" + "".join(rows) + "</table>"


def _html_panel5(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    rows = ["<tr><th>ticket</th><th>iterations</th></tr>"]
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        rows.append('<tr><td colspan="2" class="nodata">%s</td></tr>' % NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        rows.append("<tr><td>%s</td><td>%s</td></tr>"
                    % (_esc(row.get("ticket_id", "?")), _esc(row.get("iterations", NO_DATA))))
    return "<table>" + "".join(rows) + "</table>"


def _html_panel6(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    # Bar on `input` tokens (consistent with the terminal surface's panel-6 peak).
    roles = ROLE_ORDER + tuple(_panel6_extra_roles(value))
    inputs = []
    for role in roles:
        bucket = value.get(role) if isinstance(value.get(role), dict) else {}
        inputs.append(bucket.get("input", 0))
    panel_max = _panel_max(inputs)
    rows = ["<tr><th>role</th><th>input</th><th>output</th><th>cost_usd</th>"
            "<th>token %</th><th>cost %</th><th>bar</th></tr>"]
    for role in roles:
        bucket = value.get(role) if isinstance(value.get(role), dict) else {}
        inp = bucket.get("input", 0)
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>%s</tr>"
                    % (_esc(role), _esc(inp), _esc(bucket.get("output", 0)),
                       _esc(_fmt_money(bucket.get("cost", 0), empty="-")),
                       _esc(_fmt_pct(bucket.get("token_share_pct"), NO_DATA)),
                       _esc(_fmt_pct(bucket.get("cost_share_pct"), UNAVAILABLE)),
                       _html_bar_cell(inp, panel_max)))
    return "<table>" + "".join(rows) + "</table>"


def _html_lead_cycle_cell(value):
    """One lead/cycle <td> — humanized duration, or a nodata cell when the value is "no data" (B1)."""
    formatted = _humanize_seconds(value)
    cls = ' class="nodata"' if formatted == NO_DATA else ""
    return "<td%s>%s</td>" % (cls, _esc(formatted))


def _html_panel7(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    rows = ["<tr><th>ticket</th><th>lead</th><th>cycle</th></tr>"]
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        rows.append('<tr><td colspan="3" class="nodata">%s</td></tr>' % NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        rows.append("<tr><td>%s</td>%s%s</tr>"
                    % (_esc(row.get("ticket_id", "?")),
                       _html_lead_cycle_cell(row.get("lead_seconds", NO_DATA)),
                       _html_lead_cycle_cell(row.get("cycle_seconds", NO_DATA))))
    # Two average summary rows (B1 — humanized, or a nodata cell when there is no value).
    for label, raw in (("avg lead", value.get("avg_lead_seconds", NO_DATA)),
                       ("avg cycle", value.get("avg_cycle_seconds", NO_DATA))):
        formatted = _humanize_seconds(raw)
        cls = ' class="nodata"' if formatted == NO_DATA else ""
        rows.append('<tr><td>%s</td><td colspan="2"%s>%s</td></tr>'
                    % (_esc(label), cls, _esc(formatted)))
    return "<table>" + "".join(rows) + "</table>"


_HTML_PANELS = {
    "1": _html_panel1,
    "2": _html_panel2,
    "3": _html_panel3,
    "4": _html_panel4,
    "5": _html_panel5,
    "6": _html_panel6,
    "7": _html_panel7,
}


def _html_degraded(degraded):
    parts = ['<div class="panel"><h3>Degraded</h3>']
    if not isinstance(degraded, list) or not degraded:
        parts.append('<div class="nodata">none — all panels had data</div>')
        parts.append("</div>")
        return "".join(parts)
    rows = ["<tr><th>ticket</th><th>panel</th><th>reason</th></tr>"]
    for entry in degraded:
        if not isinstance(entry, dict):
            continue
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (_esc(entry.get("ticket_id", "?")), _esc(entry.get("panel", "?")),
                       _esc(entry.get("reason", ""))))
    parts.append("<table>" + "".join(rows) + "</table>")
    parts.append("</div>")
    return "".join(parts)
