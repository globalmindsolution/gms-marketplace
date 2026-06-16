---
name: metrics
description: Render a read-only, in-session dashboard of delivery metrics for the current repo — six panels (throughput by status/type, pipeline funnel, cost and time per ticket by step, coverage achieved vs target, review iterations before pass, and token burn by role) derived from existing workspace state. Use when asked to see, audit, or report this repo's delivery throughput, funnel, spend, coverage, review effort, or token usage without leaving the session.
---

You are the coordinator of `/acs:metrics`, the acs delivery dashboard. This is
NOT a hooked pipeline skill: no skill-start, no pre/post hooks, no subagents, no
reflection loop. You do everything yourself with Bash and `show_widget`.

Scope honesty up front: this skill is **read-only**. It aggregates metrics that
already exist in the workspace and renders them inline — it writes no file,
makes no network call, runs no `gh`/HTTP, and reads no config key beyond the
`.acs/settings.json` the helper already consumes. The only side effect is the
inline render in this session. The aggregation lives entirely in the helper
(`hooks/scripts/metrics_aggregate.py`); your job is to run it, parse its JSON,
and draw the panels.

`show_widget` is a main-session-only tool — it is not available to subagents,
which is precisely why this skill renders inline itself and delegates nothing.

## Step 1 — Run the aggregation helper

Run the helper via Bash. It takes no required arguments — it resolves the live
repo and workspace itself (via `acs_lib.build_context()`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/metrics_aggregate.py"
```

The helper exits `0` even on an empty or partial workspace — degradation is
in-band (`meta.degraded`), never an error code. Parse the JSON object it prints
to stdout. Its shape is:

```json
{
  "panels": { "1": …, "2": …, "3": …, "4": …, "5": …, "6": … },
  "meta": { "generated_at": …, "repo_id": …, "ticket_count": …, "degraded": [ … ] }
}
```

**Every panel key `"1"`–`"6"` is ALWAYS present** (the helper's invariant):
degradation is a `"no data"` marker inside a panel, never a missing key. So you
can always draw all six frames. If the helper exits non-zero (an unexpected
internal error), report that the dashboard could not be generated and stop —
do not fabricate panels.

## Step 2 — Render all six panels in ONE `show_widget` call

Compose a **single** `show_widget` dashboard that draws all six panel frames
from `panels["1"]`…`panels["6"]`, plus a header from the `meta` block
(`repo_id`, `generated_at`, `ticket_count`). Because every panel key is always
present, the widget always renders six frames — an empty or partial workspace
shows the affected frame as "no data" rather than omitting it. Never split the
dashboard across multiple `show_widget` calls; it is one dashboard.

The six panels, in order:

1. **Throughput** — ticket counts by status and by type.
2. **Pipeline funnel** — how many tickets reached each pipeline step, with the
   PR/merge counts as the terminus.
3. **Cost + time per ticket by step** — per-ticket rows broken down by pipeline
   step (working time and spend), with the repo total.
4. **Coverage achieved vs target** — per ticket; a `null`/`"n/a"` coverage
   renders as "no data" for that ticket, never a crash or a fabricated number.
5. **Review iterations before the verifier passed** — per-ticket integer.
6. **Token burn by role** — input/output tokens and cost bucketed into the three
   roles planner / executor / verifier.

Surface the `meta.degraded` entries somewhere visible in the dashboard (which
ticket/panel fell back to "no data" and why) so the render is auditable — a
reader can see what was missing rather than mistaking a gap for a zero.

## Step 3 — Markdown-table fallback when `show_widget` is unavailable

`show_widget` is the intended renderer, but if it is unavailable in this
session, do NOT fail: render the **same six panels as a Markdown table** in your
reply, including the same `meta` header and the same `degraded` annotations.
The dashboard must still appear inline either way — the fallback is content
parity, not a degraded summary.

## Completion report (normative)

End your final message with the standard completion block; replace the Ticket
line with **Scope** (this skill is repo-wide, not tied to one ticket):

```markdown
## /acs:metrics · <status>

- **Scope**: delivery dashboard for <repo_id> (<ticket_count> tickets, generated <generated_at>)
- **Status**: <status> — <one line>
- **Results**: six panels rendered inline via show_widget (or Markdown-table fallback)
- **Findings**: <degraded panels/tickets and why, or "none — all panels had data">
- **Artifacts**: none (this skill writes nothing)
- **Metrics**: n/a
- **Next**: <e.g. re-run after the next ticket completes, or drill into a flagged ticket>
```
