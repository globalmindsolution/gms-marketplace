#!/usr/bin/env python3
"""metrics_render.py — deterministic cross-surface renderer for the /acs:metrics dashboard (MAR-5).

Stdlib-only (Python 3.9+, no pip; NEVER imports show_widget). Consumes the spec-01 aggregate JSON
({panels:{"1".."7"}, meta:{generated_at, repo_id, ticket_count, degraded}}) emitted by
metrics_aggregate.py and renders the SAME seven panels for TWO surfaces:

    render_terminal(data) -> str   deterministic Unicode block-bar terminal dashboard (CLI default)
    render_html(data)     -> str   ONE self-contained HTML string (Desktop/claude.ai; handed to
                                   show_widget verbatim) — inline CSS only, NO external fetch.

MAR-14 spec 02 extends this module with two-view entrypoints:

    render_pm_terminal(data) -> str   PM view: delivery_summary,1,2,issues,progress,deadline,4,5,7
    render_pm_html(data)     -> str   PM view HTML (self-contained)
    render_usage_terminal(data) -> str   usage view: usage_summary,3,6,usage_by_model,usage_by_ticket
    render_usage_html(data)    -> str   usage view HTML (self-contained)

A --view {pm,usage,all} CLI flag selects the view. Default is pm (clarification C-2 — see note
in main()). --view all routes to render_terminal/render_html (full-panel back-compat).

Plus a thin main() that reads the aggregate JSON from stdin (json.load) — or self-invokes
metrics_aggregate.aggregate via acs_lib.build_context when stdin is empty — picks the surface
(terminal by default, HTML on --html), prints it to stdout, and returns 0.

This is the C-7 deterministic cross-surface renderer that SUPERSEDES the model-improvised
Markdown fallback (former ledger C-4). The aggregate-JSON contract (spec 01 / A1) is UNCHANGED —
no field added, no key renamed; the panel value shapes are exactly those metrics_aggregate emits.

Invariants (AC-8):
  * B1 — every panel key "1".."7" is ALWAYS rendered as a framed section; a bare "no data" panel
    draws a "no data" frame and a cell-level {"cell"/"iterations": "no data"} draws a "no data"
    cell — never an omitted frame.
  * Determinism — identical JSON in -> byte-identical output. The renderer reads NO clock and
    generates NO random value; meta.generated_at is rendered EXACTLY as given (it is the
    aggregator that stamps it). Every dict is iterated in a fixed, reproducible order.
  * Read-only — zero writes (no file, no state, no schema/config). The only effects of main() are
    reading stdin and printing to stdout.
  * Never crash — a panel value is sometimes a dict and sometimes the bare string "no data"; the
    renderer renders a "no data" frame for either form on both surfaces and never raises (the
    never-crash discipline of statusline.py).

ANSI color is OFF by default (determinism forbids surface-dependent escapes in the golden output).
"""

import argparse
import html as _html
import json
import os
import sys
import acs_lib  # noqa: E402

# The module split (MAR-531) is invisible to every caller: this file stays the
# entry point the SKILL.md files invoke and the module the tests import, and
# re-exports the whole pre-split surface -- private helpers included, because
# the golden tests reach them by name. Import from the module that OWNS a name
# when you add code; import from here only to keep an existing caller working.
from metrics_render_common import (AVERAGE_ROWS, NO_DATA, PANEL_KEYS, PANEL_TITLES,
    ROLE_ORDER, UNAVAILABLE, _BAR_EMPTY, _BAR_FULL,
    _BAR_WIDTH, _NEW_PANEL_TITLES, _PM_PANELS,
    _USAGE_PANELS, _average_cells, _bar, _bar_pct,
    _counts_items, _esc, _fmt_money, _fmt_pct,
    _format_average, _html_bar_cell, _humanize_ms,
    _humanize_seconds, _is_no_data, _meta_lines,
    _panel6_extra_roles, _panel_max,
    _ticket_api_duration_str)  # noqa: F401
from metrics_render_terminal import (_TERMINAL_PANELS, _term_no_data_block, _term_panel1,
    _term_panel2, _term_panel3, _term_panel3_sub_rows,
    _term_panel4, _term_panel5, _term_panel6,
    _term_panel7, _terminal_degraded, render_terminal)  # noqa: F401
from metrics_render_html import (_HTML_PANELS, _HTML_STYLE, _html_counts_table,
    _html_degraded, _html_lead_cycle_cell, _html_no_data,
    _html_panel1, _html_panel2, _html_panel3,
    _html_panel3_sub_rows, _html_panel4, _html_panel5,
    _html_panel6, _html_panel7, render_html)  # noqa: F401
from metrics_render_panels import (_html_render_deadline, _html_render_delivery_summary,
    _html_render_issues, _html_render_progress,
    _html_render_usage_summary, _term_render_deadline,
    _term_render_delivery_summary, _term_render_issues,
    _term_render_progress, _term_render_usage_summary)  # noqa: F401
from metrics_render_tables import (_MODEL_ROW_FMT, _ROLE_ROW_FMT, _SKILL_ROW_FMT,
    _html_model_table, _html_render_usage_by_model,
    _html_render_usage_by_ticket, _html_role_table,
    _html_skill_table, _term_model_table,
    _term_render_usage_by_model,
    _term_render_usage_by_ticket, _term_role_table,
    _term_skill_table)  # noqa: F401

# Reuse acs_lib (shared scripts dir) the same way the other hooks/scripts do.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# MAR-14 spec 02 — Per-view terminal/HTML dispatch tables
# ---------------------------------------------------------------------------

# PM-view dispatch maps: existing panel keys reuse _TERMINAL_PANELS/_HTML_PANELS;
# new panel keys map to the new renderers defined above.
_PM_TERMINAL_PANELS = {
    "delivery_summary": _term_render_delivery_summary,
    "1": _term_panel1,
    "2": _term_panel2,
    "issues": _term_render_issues,
    "progress": _term_render_progress,
    "deadline": _term_render_deadline,
    "4": _term_panel4,
    "5": _term_panel5,
    "7": _term_panel7,
}

_PM_HTML_PANELS = {
    "delivery_summary": _html_render_delivery_summary,
    "1": _html_panel1,
    "2": _html_panel2,
    "issues": _html_render_issues,
    "progress": _html_render_progress,
    "deadline": _html_render_deadline,
    "4": _html_panel4,
    "5": _html_panel5,
    "7": _html_panel7,
}

# Usage-view dispatch maps.
_USAGE_TERMINAL_PANELS = {
    "usage_summary": _term_render_usage_summary,
    "3": _term_panel3,
    "6": _term_panel6,
    "usage_by_model": _term_render_usage_by_model,
    "usage_by_ticket": _term_render_usage_by_ticket,
}

_USAGE_HTML_PANELS = {
    "usage_summary": _html_render_usage_summary,
    "3": _html_panel3,
    "6": _html_panel6,
    "usage_by_model": _html_render_usage_by_model,
    "usage_by_ticket": _html_render_usage_by_ticket,
}


# ---------------------------------------------------------------------------
# MAR-14 spec 02 — View-scoped entrypoints (pure; no I/O, no clock)
# ---------------------------------------------------------------------------

def render_pm_terminal(data):
    """PM-view terminal dashboard (delivery_summary,1,2,issues,progress,deadline,4,5,7). Never raises."""
    data = data if isinstance(data, dict) else {}
    panels = data.get("panels") if isinstance(data.get("panels"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}

    lines = []
    lines.append("=" * 60)
    lines.append("/acs:metrics dashboard — PM view")
    for ml in _meta_lines(meta):
        lines.append("  " + ml)
    lines.append("=" * 60)

    for key in _PM_PANELS:
        lines.append("")
        title = _NEW_PANEL_TITLES.get(key) or PANEL_TITLES.get(key, key)
        lines.append(title)
        lines.append("-" * 60)
        value = panels.get(key, NO_DATA)
        renderer = _PM_TERMINAL_PANELS[key]
        lines.extend(renderer(value))

    lines.append("")
    lines.extend(_terminal_degraded(meta.get("degraded")))
    return "\n".join(lines) + "\n"


def render_pm_html(data):
    """PM-view self-contained HTML dashboard. Inline CSS, no fetch. Never raises."""
    data = data if isinstance(data, dict) else {}
    panels = data.get("panels") if isinstance(data.get("panels"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}

    parts = ['<div class="acs-metrics">']
    parts.append(_HTML_STYLE)
    parts.append("<h2>/acs:metrics dashboard — PM view</h2>")
    parts.append('<div class="meta">')
    parts.append(" &middot; ".join(_esc(ml) for ml in _meta_lines(meta)))
    parts.append("</div>")

    for key in _PM_PANELS:
        title = _NEW_PANEL_TITLES.get(key) or PANEL_TITLES.get(key, key)
        value = panels.get(key, NO_DATA)
        parts.append('<div class="panel">')
        parts.append("<h3>%s</h3>" % _esc(title))
        parts.append(_PM_HTML_PANELS[key](value))
        parts.append("</div>")

    parts.append(_html_degraded(meta.get("degraded")))
    parts.append("</div>")
    return "".join(parts)


def render_usage_terminal(data):
    """Usage-view terminal dashboard (usage_summary,3,6). Never raises."""
    data = data if isinstance(data, dict) else {}
    panels = data.get("panels") if isinstance(data.get("panels"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}

    lines = []
    lines.append("=" * 60)
    lines.append("/acs:usage dashboard — usage view")
    for ml in _meta_lines(meta):
        lines.append("  " + ml)
    lines.append("=" * 60)

    for key in _USAGE_PANELS:
        lines.append("")
        title = _NEW_PANEL_TITLES.get(key) or PANEL_TITLES.get(key, key)
        lines.append(title)
        lines.append("-" * 60)
        value = panels.get(key, NO_DATA)
        renderer = _USAGE_TERMINAL_PANELS[key]
        lines.extend(renderer(value))

    lines.append("")
    lines.extend(_terminal_degraded(meta.get("degraded")))
    return "\n".join(lines) + "\n"


def render_usage_html(data):
    """Usage-view self-contained HTML dashboard. Inline CSS, no fetch. Never raises."""
    data = data if isinstance(data, dict) else {}
    panels = data.get("panels") if isinstance(data.get("panels"), dict) else {}
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}

    parts = ['<div class="acs-metrics">']
    parts.append(_HTML_STYLE)
    parts.append("<h2>/acs:usage dashboard — usage view</h2>")
    parts.append('<div class="meta">')
    parts.append(" &middot; ".join(_esc(ml) for ml in _meta_lines(meta)))
    parts.append("</div>")

    for key in _USAGE_PANELS:
        title = _NEW_PANEL_TITLES.get(key) or PANEL_TITLES.get(key, key)
        value = panels.get(key, NO_DATA)
        parts.append('<div class="panel">')
        parts.append("<h3>%s</h3>" % _esc(title))
        parts.append(_USAGE_HTML_PANELS[key](value))
        parts.append("</div>")

    parts.append(_html_degraded(meta.get("degraded")))
    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# CLI: stdin (primary) or self-invoke aggregate (fallback); terminal default, --html on flag
# ---------------------------------------------------------------------------

def _load_payload():
    """Read the aggregate JSON from stdin when piped; else self-invoke metrics_aggregate."""
    stdin = sys.stdin
    piped = False
    try:
        piped = not stdin.isatty()
    except (ValueError, AttributeError):
        piped = True
    if piped:
        raw = stdin.read()
        if raw and raw.strip():
            return json.loads(raw)
    # Secondary — self-invoke the aggregator (no piped input).
    import metrics_aggregate
    ctx = acs_lib.build_context(os.getcwd())
    return metrics_aggregate.aggregate(ctx["workspace"], ctx["repo_id"])


def main():
    """Read the payload, render the chosen view+surface, print, exit 0.

    DELIBERATE DEVIATION (clarification C-2, MAR-14 spec 02): bare invocation with NO --view flag
    now defaults to the PM view (render_pm_terminal / render_pm_html), NOT the full seven-panel
    dashboard described at MAR-8/design.md:687-689. Use --view all for the full-panel back-compat
    path (render_terminal / render_html). This deviation is sanctioned by clarification C-2.
    """
    parser = argparse.ArgumentParser(description="Render /acs:metrics dashboard")
    parser.add_argument("--html", action="store_true",
                        help="Render HTML output (default: terminal)")
    parser.add_argument(
        "--view",
        choices=["pm", "usage", "all"],
        default="pm",
        help="Select view: pm (default), usage, or all (full-panel back-compat).",
    )
    args, _ = parser.parse_known_args()

    data = _load_payload()

    if args.view == "usage":
        output = render_usage_html(data) if args.html else render_usage_terminal(data)
    elif args.view == "all":
        output = render_html(data) if args.html else render_terminal(data)
    else:
        # Default: pm (C-2 deviation from design:687-689 — see docstring above)
        output = render_pm_html(data) if args.html else render_pm_terminal(data)

    sys.stdout.write(output)
    if not output.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
