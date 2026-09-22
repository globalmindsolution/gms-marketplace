"""metrics_render_terminal — the deterministic Unicode terminal surface
(extracted from metrics_render.py by MAR-531).

One renderer per spec-01 panel plus the frame helpers, unchanged. ANSI colour
stays off: a surface-dependent escape would break the golden output.
"""


import acs_lib  # noqa: E402

from metrics_render_common import NO_DATA, PANEL_KEYS, PANEL_TITLES, ROLE_ORDER, UNAVAILABLE, _average_cells, _bar, _counts_items, _fmt_money, _fmt_pct, _humanize_ms, _humanize_seconds, _is_no_data, _meta_lines, _panel6_extra_roles



# ---------------------------------------------------------------------------
# Terminal surface (default) — deterministic Unicode, no ANSI, no color
# ---------------------------------------------------------------------------

def render_terminal(data):
    """Deterministic Unicode block-bar dashboard for ALL SEVEN panels (CLI default). Never raises."""
    data = data if isinstance(data, dict) else {}
    panels = data.get("panels") if isinstance(data.get("panels"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}

    lines = []
    lines.append("=" * 60)
    lines.append("/acs:metrics dashboard")
    for ml in _meta_lines(meta):
        lines.append("  " + ml)
    lines.append("=" * 60)

    for key in PANEL_KEYS:
        lines.append("")
        lines.append(PANEL_TITLES[key])
        lines.append("-" * 60)
        value = panels.get(key, NO_DATA)
        renderer = _TERMINAL_PANELS[key]
        lines.extend(renderer(value))

    lines.append("")
    lines.extend(_terminal_degraded(meta.get("degraded")))
    return "\n".join(lines) + "\n"


def _term_no_data_block():
    return ["  " + NO_DATA]


def _term_panel1(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    out = ["  by status:"]
    status_items = _counts_items(value.get("by_status"))
    type_items = _counts_items(value.get("by_type"))
    peak = max([c for _, c in status_items + type_items if isinstance(c, (int, float))] or [0])
    if not status_items:
        out.append("    " + NO_DATA)
    for label, count in status_items:
        out.append("    %-14s %s %s" % (label, _bar(count, peak), count))
    out.append("  by type:")
    if not type_items:
        out.append("    " + NO_DATA)
    for label, count in type_items:
        out.append("    %-14s %s %s" % (label, _bar(count, peak), count))
    return out


def _term_panel2(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    steps = value.get("steps") if isinstance(value.get("steps"), dict) else {}
    out = ["  funnel (tickets reaching each step):"]
    # Fixed order: the canonical HOOKED_SKILLS order.
    counts = [steps.get(skill, 0) for skill in acs_lib.HOOKED_SKILLS]
    peak = max([c for c in counts if isinstance(c, (int, float))] or [0])
    for skill in acs_lib.HOOKED_SKILLS:
        count = steps.get(skill, 0)
        out.append("    %-14s %s %s" % (skill, _bar(count, peak), count))
    prs = value.get("prs") if isinstance(value.get("prs"), dict) else {}
    out.append("  PRs:  created %s   merged %s"
               % (prs.get("created", 0), prs.get("merged", 0)))
    return out


def _term_panel3_sub_rows(row):
    """Per-skill sub-rows (MAR-7 spec 02, D5.4/S-C): "step span" (from `steps`, unchanged
    mechanism) + API duration/basis (from `step_api_duration`), one line per `step_order` entry.
    A missing/non-list `step_order` (legacy pre-MAR-7 aggregate JSON) yields no sub-rows at all."""
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
        out.append("    %-14s step span %10s   api duration %s" % (skill, step_span, api_str))
    return out


def _term_panel3(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    rows = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    out = ["  %-12s %12s %12s" % ("ticket", "working time", "cost_usd")]
    if not rows:
        out.append("  " + NO_DATA)
    for row in rows:
        if not isinstance(row, dict):
            continue
        totals = row.get("totals") if isinstance(row.get("totals"), dict) else {}
        # C-6: humanize the working time; a missing/non-numeric value still renders the
        # existing no-data cell (B1 — _humanize_seconds returns NO_DATA for any non-number).
        working_time = _humanize_seconds(totals.get("working_seconds", "-"))
        cost = _fmt_money(totals.get("cost_usd", "-"), empty="-")
        out.append("  %-12s %12s %12s" % (str(row.get("ticket_id", "?")), working_time, cost))
        out.extend(_term_panel3_sub_rows(row))
    repo_totals = value.get("repo_totals") if isinstance(value.get("repo_totals"), dict) else {}
    if repo_totals:
        out.append("  %-12s %12s %12s"
                   % ("REPO TOTAL", _humanize_seconds(repo_totals.get("working_seconds", "-")),
                      _fmt_money(repo_totals.get("cost_usd", "-"), empty="-")))
    # Four averages summary rows after REPO TOTAL (B1 — each value present, "no data" when absent).
    for label, formatted in _average_cells(value):
        out.append("  %-30s %12s" % (label, formatted))
    return out


def _term_panel4(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    rows = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    out = ["  %-12s %10s %10s %8s" % ("ticket", "achieved", "target", "passed")]
    if not rows:
        out.append("  " + NO_DATA)
    for row in rows:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("ticket_id", "?"))
        if row.get("cell") == NO_DATA or "achieved" not in row:
            out.append("  %-12s %10s" % (tid, NO_DATA))
            continue
        out.append("  %-12s %10s %10s %8s"
                   % (tid, row.get("achieved"), row.get("target"),
                      "yes" if row.get("passed") else "no"))
    return out


def _term_panel5(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    rows = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    out = ["  %-12s %12s" % ("ticket", "iterations")]
    if not rows:
        out.append("  " + NO_DATA)
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append("  %-12s %12s"
                   % (str(row.get("ticket_id", "?")), row.get("iterations", NO_DATA)))
    return out


def _term_panel6(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    out = ["  %-10s %12s %12s %10s %10s %10s" % ("role", "input", "output", "cost_usd",
                                                   "token %", "cost %")]
    roles = ROLE_ORDER + tuple(_panel6_extra_roles(value))
    inputs = []
    for role in roles:
        bucket = value.get(role) if isinstance(value.get(role), dict) else {}
        if isinstance(bucket.get("input"), (int, float)):
            inputs.append(bucket.get("input"))
    peak = max(inputs or [0])
    for role in roles:
        bucket = value.get(role) if isinstance(value.get(role), dict) else {}
        inp = bucket.get("input", 0)
        out.append("  %-10s %12s %12s %10s %10s %10s   %s"
                   % (role, inp, bucket.get("output", 0),
                      _fmt_money(bucket.get("cost", 0), empty="-"),
                      _fmt_pct(bucket.get("token_share_pct"), NO_DATA),
                      _fmt_pct(bucket.get("cost_share_pct"), UNAVAILABLE),
                      _bar(inp, peak)))
    return out


def _term_panel7(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    rows = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    out = ["  %-12s %12s %12s" % ("ticket", "lead", "cycle")]
    if not rows:
        out.append("  " + NO_DATA)
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append("  %-12s %12s %12s"
                   % (str(row.get("ticket_id", "?")),
                      _humanize_seconds(row.get("lead_seconds", NO_DATA)),
                      _humanize_seconds(row.get("cycle_seconds", NO_DATA))))
    # Two average summary rows (B1 — humanized, or a "no data" cell when there is no value).
    out.append("  %-30s %12s" % ("avg lead", _humanize_seconds(value.get("avg_lead_seconds", NO_DATA))))
    out.append("  %-30s %12s" % ("avg cycle", _humanize_seconds(value.get("avg_cycle_seconds", NO_DATA))))
    return out


_TERMINAL_PANELS = {
    "1": _term_panel1,
    "2": _term_panel2,
    "3": _term_panel3,
    "4": _term_panel4,
    "5": _term_panel5,
    "6": _term_panel6,
    "7": _term_panel7,
}


def _terminal_degraded(degraded):
    out = ["Degraded (panels that fell back to 'no data'):", "-" * 60]
    if not isinstance(degraded, list) or not degraded:
        out.append("  none — all panels had data")
        return out
    for entry in degraded:
        if not isinstance(entry, dict):
            continue
        out.append("  %s  panel %s  %s"
                   % (entry.get("ticket_id", "?"), entry.get("panel", "?"),
                      entry.get("reason", "")))
    return out
