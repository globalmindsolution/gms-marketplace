"""metrics_aggregate_common — numeric coercion, averages and date parsing
(extracted from metrics_aggregate.py by MAR-531).

The total-by-construction primitives every panel builder leans on: a value that
is absent, wrong-typed or unparseable yields None or the documented default,
never an exception, so the aggregator degrades a cell instead of a run.
"""


import re
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

    Thin delegate over acs_lib.metrics.elapsed_seconds, the single shared primitive both this
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
    # Reached through the OWNING module, not the facade: acs_lib is a package
    # (MAR-522) and acs_lib.run_seconds calls acs_lib.metrics.elapsed_seconds,
    # so naming the same binding here keeps the two adapters over one primitive.
    return acs_lib.metrics.elapsed_seconds(start_iso, end_iso)


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


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""
