"""metrics_render_common — panel titles, formatters and the pure helpers
both surfaces share (extracted from metrics_render.py by MAR-531).

No I/O, no clock, no randomness: every name here is a pure function of its
arguments, which is what lets the terminal and HTML surfaces stay
byte-deterministic for identical input.
"""


import argparse
import html as _html
import json
import os
import sys
import acs_lib  # noqa: E402


PANEL_KEYS = ("1", "2", "3", "4", "5", "6", "7")

# ---------------------------------------------------------------------------
# MAR-14 spec 02 — PM and usage view allowlists (AC-5: strict partition)
# These two tuples PARTITION the full rendered panel set: no key appears in both,
# together they cover every rendered panel.
# ---------------------------------------------------------------------------

# PM view panels — in display order (design pinned allocation MAR-8/design.md:359-383)
_PM_PANELS = (
    "delivery_summary",
    "1",
    "2",
    "issues",
    "progress",
    "deadline",
    "4",
    "5",
    "7",
)

# Usage view panels — in display order (design pinned allocation MAR-8/design.md:376-378;
# usage_by_model appended per MAR-3 spec 05; usage_by_ticket appended per MAR-4 spec 02).
_USAGE_PANELS = (
    "usage_summary",
    "3",
    "6",
    "usage_by_model",
    "usage_by_ticket",
)

# Canonical, fixed iteration orders (determinism — never rely on dict insertion order).
# These four roles are ALWAYS present in the aggregate's panel-6 value dict (metrics_aggregate.py
# seeds all four up front); "other"/"unattributed" are NOT always present (_accumulate_burn only
# setdefaults them when such usage exists), so they are never added here — panel 6 derives them
# dynamically from whatever extra keys actually appear in the value dict at render time.
ROLE_ORDER = ("planner", "executor", "verifier", "coordinator")

PANEL_TITLES = {
    "1": "Panel 1 — Throughput by status / type",
    "2": "Panel 2 — Pipeline funnel",
    "3": "Panel 3 — Cost + time per ticket by step",
    "4": "Panel 4 — Coverage achieved vs target",
    "5": "Panel 5 — Review iterations before pass",
    "6": "Panel 6 — Token burn by role",
    "7": "Panel 7 — Lead + cycle time per ticket",
}

# New panel titles (MAR-14 spec 02)
_NEW_PANEL_TITLES = {
    "delivery_summary": "Delivery Summary",
    "issues": "Issues",
    "progress": "Progress",
    "deadline": "Deadline",
    "usage_summary": "Usage Summary",
    "usage_by_model": "Usage by model",
    "usage_by_ticket": "Usage by ticket",
}

# Fixed-key order for the Panel 3 averages summary rows (determinism — read by name, not by
# dict iteration). The aggregate (spec 01) emits exactly these four keys.
AVERAGE_ROWS = (
    ("avg working time / ticket", "avg_working_seconds_per_ticket", "duration"),
    ("avg working time / merged PR", "avg_working_seconds_per_pr", "duration"),
    ("avg cost / ticket", "avg_cost_per_ticket", "cost"),
    ("avg cost / merged PR", "avg_cost_per_pr", "cost"),
)

NO_DATA = "no data"

# Cost-share-only null marker (MAR-4 spec 02, D6): distinct from NO_DATA. Used ONLY by a
# cost-share cell whose value is None (an unavailable cost basis) -- a token-share cell's
# None still renders NO_DATA, its own separate convention.
UNAVAILABLE = "unavailable"

# Unicode block glyphs for the deterministic block-bar (statusline.py's deterministic-glyph style).
_BAR_FULL = "█"   # █
_BAR_EMPTY = "·"  # ·
_BAR_WIDTH = 24        # fixed bar width so output is deterministic regardless of value magnitude


# ---------------------------------------------------------------------------
# Shared helpers (pure; no I/O, no clock)
# ---------------------------------------------------------------------------

def _is_no_data(value):
    """A panel/cell value that means 'no data' (the bare string, the whole-panel empty form)."""
    return value == NO_DATA


def _bar(value, peak):
    """A fixed-width Unicode block bar for `value` relative to `peak` (peak<=0 -> empty bar)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or peak <= 0:
        filled = 0
    else:
        filled = int(round((value / peak) * _BAR_WIDTH))
        filled = max(0, min(_BAR_WIDTH, filled))
    return _BAR_FULL * filled + _BAR_EMPTY * (_BAR_WIDTH - filled)


def _humanize_seconds(value):
    """Format a seconds count as a human-readable duration, or NO_DATA for any non-number.

    Pure function of its argument only — NO clock, NO locale, NO random (determinism / R4).
    A numeric value renders the two most significant non-zero units in descending order
    (d/h/m/s), e.g. "2d 3h", "3h 4m", "5m 12s", "12s", "0s". bool (an int subclass) and any
    non-numeric value (including the literal NO_DATA string) return NO_DATA — this is what makes
    the "no data" cell appear (B1). Mirrors the bool guard in _bar/_bar_pct.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return NO_DATA
    total = int(value)
    sign = "-" if total < 0 else ""
    total = abs(total)
    units = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
    parts = []
    remaining = total
    for label, size in units:
        count = remaining // size
        remaining -= count * size
        if count or (label == "s" and not parts):
            parts.append("%d%s" % (count, label))
    # Two most significant units; "0s" for an all-zero duration (parts is then just ["0s"]).
    return sign + " ".join(parts[:2])


def _humanize_ms(value):
    """Format a millisecond duration (MAR-7 spec 02): converts to seconds, then delegates to
    _humanize_seconds for the actual formatting. NO_DATA for any non-number, same guard."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return NO_DATA
    return _humanize_seconds(value / 1000.0)


def _fmt_money(value, empty=NO_DATA):
    """Format a USD cost cell to EXACTLY 2 decimals, or the cell's empty marker for any non-number.

    Pure function of its arguments only — NO clock, NO locale, NO random (determinism / R4).
    A numeric value renders "%.2f" (e.g. 36.0 -> "36.00", 5.142857... -> "5.14", 7.2 -> "7.20").
    bool (an int subclass) and any non-numeric value (the literal NO_DATA string, a missing-cell
    default, None) return `empty` — the marker the calling cell uses for its empty state (NO_DATA
    for the average cells, "-" for the per-ticket / REPO-TOTAL / role cost columns), so the cell's
    existing empty handling and B1 ("no data" cells still render) are preserved. Mirrors the bool
    guard in _humanize_seconds.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return empty
    return "%.2f" % value


def _fmt_pct(value, empty):
    """Format a percentage cell to EXACTLY 1 decimal + '%', or `empty` for any non-number.

    Mirrors _fmt_money's house style: a numeric, non-bool `value` renders "%.1f%%" (e.g.
    12.5 -> "12.5%"). bool (an int subclass) and any non-numeric value (None, the literal
    NO_DATA string) return `empty` -- the caller's own marker (NO_DATA for token_share_pct,
    UNAVAILABLE for cost_share_pct). No division here (D2 placement) -- the value arrives
    pre-computed from metrics_aggregate.py; this only formats.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return empty
    return "%.1f%%" % value


def _meta_lines(meta):
    """The header lines drawn from meta (rendered as given — generated_at is data, no clock read)."""
    meta = meta if isinstance(meta, dict) else {}
    return [
        "repo: %s" % meta.get("repo_id", ""),
        "generated_at: %s" % meta.get("generated_at", ""),
        "tickets: %s" % meta.get("ticket_count", 0),
    ]


def _counts_items(mapping):
    """Sorted (label, count) pairs from a {label: int} mapping — fixed order for determinism."""
    if not isinstance(mapping, dict):
        return []
    return sorted(((str(k), v) for k, v in mapping.items()), key=lambda kv: kv[0])


def _format_average(value, kind):
    """Format a Panel-3 average cell: duration averages humanized, cost averages numeric.

    A "no data" (or any non-numeric) value renders the NO_DATA cell for either kind (B1).
    """
    if _is_no_data(value):
        return NO_DATA
    if kind == "duration":
        return _humanize_seconds(value)
    # kind == "cost": money to exactly 2 decimals; non-numeric -> NO_DATA cell (B1).
    return _fmt_money(value, empty=NO_DATA)


def _average_cells(value):
    """The (label, formatted_value) pairs for Panel 3's four averages (fixed order, B1).

    A missing or non-dict `averages` renders four NO_DATA cells — never an omitted row.
    """
    averages = value.get("averages") if isinstance(value, dict) else None
    averages = averages if isinstance(averages, dict) else {}
    out = []
    for label, key, kind in AVERAGE_ROWS:
        out.append((label, _format_average(averages.get(key, NO_DATA), kind)))
    return out


def _panel6_extra_roles(value):
    """Extra panel-6 keys beyond ROLE_ORDER ("other"/"unattributed" when present), sorted."""
    return sorted(k for k in value if k not in ROLE_ORDER)


def _esc(value):
    """HTML-escape any scalar to text (quotes too) — defends the document frame."""
    return _html.escape(str(value), quote=True)


def _bar_pct(value, panel_max):
    """Deterministic integer bar percent: round(value / panel_max * 100), clamped 0..100.

    panel_max <= 0 (or a non-numeric / bool value) yields 0 — never divides by zero.
    """
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not isinstance(panel_max, (int, float)) or isinstance(panel_max, bool)
            or panel_max <= 0):
        return 0
    pct = int(round((value / panel_max) * 100))
    return max(0, min(100, pct))


def _html_bar_cell(value, panel_max):
    """A theme-adaptive CSS bar cell sized width:N% (integer percent) for `value`.

    Rendered as a fixed-width track holding a deterministic fill; panel_max <= 0
    (or a non-numeric value) renders a 0-width fill rather than dividing by zero.
    """
    pct = _bar_pct(value, panel_max)
    return ('<td><span class="acs-bar-track">'
            '<span class="acs-bar" style="width:%d%%"></span></span></td>') % pct


def _panel_max(values):
    """The max numeric value in `values` (bools/non-numerics ignored); 0 when none."""
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return max(nums) if nums else 0


def _ticket_api_duration_str(row):
    """Ticket-scope api_duration_ms/api_duration_basis header value (MAR-7 spec 02) — shared by
    both surfaces' usage_by_ticket renderers."""
    basis = row.get("api_duration_basis")
    if basis == "unavailable":
        return UNAVAILABLE
    return _humanize_ms(row.get("api_duration_ms"))
