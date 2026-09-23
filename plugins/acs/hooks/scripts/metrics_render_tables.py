"""metrics_render_tables — the usage_by_model and usage_by_ticket tables,
both surfaces (extracted from metrics_render.py by MAR-531).

These are the widest output the dashboard produces (a model row carries five
columns and a role row six), so their column formats and the table builders
sit together rather than inside the surface modules.
"""



from metrics_render_common import NO_DATA, _esc, _fmt_pct, _humanize_seconds, _is_no_data
from metrics_render_terminal import _term_no_data_block
from metrics_render_html import _html_no_data



# ---------------------------------------------------------------------------
# MAR-3 spec 05 — "Usage by model" table (AC-2, render half): repo scope then one
# section per ticket, from panels.usage_by_model's {repo, tickets} shape (design.md:733-744).
# Token counts only; no division is performed here.
# ---------------------------------------------------------------------------

_MODEL_ROW_FMT = "%s%-28s %10s %10s %12s %12s"


def _term_model_table(models, indent):
    """Rendered lines for one models list (a 'no data' string/missing key/empty list -> one cell)."""
    out = [_MODEL_ROW_FMT % (indent, "model", "input", "output", "cache write", "cache read")]
    if _is_no_data(models) or not isinstance(models, list) or not models:
        out.append(indent + NO_DATA)
        return out
    for row in models:
        if not isinstance(row, dict):
            continue
        out.append(_MODEL_ROW_FMT % (
            indent, str(row.get("model", "?")), row.get("input", 0), row.get("output", 0),
            row.get("cache_creation", 0), row.get("cache_read", 0)))
    return out


def _term_render_usage_by_model(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    out = ["  repo:"]
    out.extend(_term_model_table(value.get("repo"), indent="    "))
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        out.append("  " + NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        out.append("  ticket %s:" % row.get("ticket_id", "?"))
        out.extend(_term_model_table(row.get("models"), indent="    "))
    return out


def _html_model_table(models):
    """Rendered <table> for one models list (a 'no data' string/missing key/empty list -> nodata row)."""
    rows = ["<tr><th>model</th><th>input</th><th>output</th><th>cache write</th>"
            "<th>cache read</th></tr>"]
    if _is_no_data(models) or not isinstance(models, list) or not models:
        rows.append('<tr><td colspan="5" class="nodata">%s</td></tr>' % NO_DATA)
        return "<table>" + "".join(rows) + "</table>"
    for row in models:
        if not isinstance(row, dict):
            continue
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (_esc(row.get("model", "?")), _esc(row.get("input", 0)),
                       _esc(row.get("output", 0)), _esc(row.get("cache_creation", 0)),
                       _esc(row.get("cache_read", 0))))
    return "<table>" + "".join(rows) + "</table>"


def _html_render_usage_by_model(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    parts = ["<h4>repo</h4>", _html_model_table(value.get("repo"))]
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        parts.append('<div class="nodata">%s</div>' % NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        parts.append("<h4>ticket %s</h4>" % _esc(row.get("ticket_id", "?")))
        parts.append(_html_model_table(row.get("models")))
    return "".join(parts)


# ---------------------------------------------------------------------------
# MAR-4 spec 02 — "Usage by ticket" table: one role-share table per ticket, from
# panels.usage_by_ticket's {"tickets": [{"ticket_id", "roles"}, ...]} shape (design.md:750-758).
# No division is performed here — the percentages arrive pre-computed from
# metrics_aggregate.py (D2 placement); roles are rendered in the dict's OWN key order
# (already sorted by the aggregator) — never re-sorted here.
# ---------------------------------------------------------------------------

_ROLE_ROW_FMT = "%s%-14s %10s %10s %12s %12s %10s"


def _term_role_table(roles):
    """Rendered lines for one ticket's roles dict (a 'no data' string/non-dict/empty dict ->
    one nodata row), following _term_model_table's exact house style."""
    out = [_ROLE_ROW_FMT % ("", "role", "input", "output", "cache write", "cache read",
                            "token %")]
    if _is_no_data(roles) or not isinstance(roles, dict) or not roles:
        out.append(NO_DATA)
        return out
    for role, bucket in roles.items():
        if not isinstance(bucket, dict):
            continue
        out.append(_ROLE_ROW_FMT % (
            "", str(role), bucket.get("input", 0), bucket.get("output", 0),
            bucket.get("cache_creation", 0), bucket.get("cache_read", 0),
            _fmt_pct(bucket.get("token_share_pct"), NO_DATA)))
    return out


def _html_role_table(roles):
    """Rendered <table> for one ticket's roles dict (a 'no data' string/non-dict/empty dict ->
    one nodata row), following _html_model_table's exact house style."""
    rows = ["<tr><th>role</th><th>input</th><th>output</th><th>cache write</th>"
            "<th>cache read</th><th>token %</th></tr>"]
    if _is_no_data(roles) or not isinstance(roles, dict) or not roles:
        rows.append('<tr><td colspan="6" class="nodata">%s</td></tr>' % NO_DATA)
        return "<table>" + "".join(rows) + "</table>"
    for role, bucket in roles.items():
        if not isinstance(bucket, dict):
            continue
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (_esc(role), _esc(bucket.get("input", 0)), _esc(bucket.get("output", 0)),
                       _esc(bucket.get("cache_creation", 0)), _esc(bucket.get("cache_read", 0)),
                       _esc(_fmt_pct(bucket.get("token_share_pct"), NO_DATA))))
    return "<table>" + "".join(rows) + "</table>"


_SKILL_ROW_FMT = "%s%-16s %22s"


def _term_skill_table(skills, indent):
    """Rendered lines for one ticket's skills[] list (MAR-7 spec 02), structural mirror of
    _term_model_table: a "no data" string/missing key/empty list -> one nodata cell. Each row's
    per-run wall-clock detail (skills[].runs[]) nests as further-indented lines directly under it."""
    out = [_SKILL_ROW_FMT % (indent, "skill", "run time (sum of runs)")]
    if _is_no_data(skills) or not isinstance(skills, list) or not skills:
        out.append(indent + NO_DATA)
        return out
    for row in skills:
        if not isinstance(row, dict):
            continue
        out.append(_SKILL_ROW_FMT % (
            indent, str(row.get("skill", "?")), _humanize_seconds(row.get("run_seconds_sum"))))
        for run in (row.get("runs") or []):
            if not isinstance(run, dict):
                continue
            out.append("%s  run %s: wall %s" % (
                indent, run.get("started_at", "?"), _humanize_seconds(run.get("wall_clock_seconds"))))
    return out


def _html_skill_table(skills):
    """Rendered <table> for one ticket's skills[] list (MAR-7 spec 02), structural mirror of
    _html_model_table. A "no data" string/missing key/empty list -> one nodata row. Each row's
    per-run detail nests as a second, smaller <table> in an extra <tr> beneath it."""
    rows = ["<tr><th>skill</th><th>run time (sum of runs)</th></tr>"]
    if _is_no_data(skills) or not isinstance(skills, list) or not skills:
        rows.append('<tr><td colspan="2" class="nodata">%s</td></tr>' % NO_DATA)
        return "<table>" + "".join(rows) + "</table>"
    for row in skills:
        if not isinstance(row, dict):
            continue
        rows.append("<tr><td>%s</td><td>%s</td></tr>"
                    % (_esc(row.get("skill", "?")), _esc(_humanize_seconds(row.get("run_seconds_sum")))))
        runs = row.get("runs") if isinstance(row.get("runs"), list) else []
        if runs:
            run_rows = ["<tr><th>started_at</th><th>wall clock</th></tr>"]
            for run in runs:
                if not isinstance(run, dict):
                    continue
                run_rows.append("<tr><td>%s</td><td>%s</td></tr>"
                                % (_esc(run.get("started_at", "?")),
                                   _esc(_humanize_seconds(run.get("wall_clock_seconds")))))
            rows.append('<tr><td></td><td><table>%s</table></td></tr>' % "".join(run_rows))
    return "<table>" + "".join(rows) + "</table>"


def _term_render_usage_by_ticket(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _term_no_data_block()
    out = []
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        out.append("  " + NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        out.append("  ticket %s:" % row.get("ticket_id", "?"))
        out.extend("    " + line for line in _term_role_table(row.get("roles")))
        out.append("    skills:")
        out.extend(_term_skill_table(row.get("skills"), indent="      "))
    return out


def _html_render_usage_by_ticket(value):
    if _is_no_data(value) or not isinstance(value, dict):
        return _html_no_data()
    parts = []
    tickets = value.get("tickets") if isinstance(value.get("tickets"), list) else []
    if not tickets:
        parts.append('<div class="nodata">%s</div>' % NO_DATA)
    for row in tickets:
        if not isinstance(row, dict):
            continue
        parts.append("<h4>ticket %s</h4>" % _esc(row.get("ticket_id", "?")))
        parts.append(_html_role_table(row.get("roles")))
        parts.append(_html_skill_table(row.get("skills")))
    return "".join(parts)
