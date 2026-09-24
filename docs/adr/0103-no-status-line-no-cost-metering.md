# 0103 — No status line, no dollar-cost metering

**Status**: Accepted — amended by [0104](0104-no-usage-dashboards-no-usage-recording.md) (the tokens this kept are no longer recorded; both dashboards are removed) · **Date**: 2026-09-23

**Supersedes in part**: [0082](0082-session-anchored-transcript-measurement-statusline-cost-apportionment.md).
Its session-anchored transcript measurement stands: tokens, `role_usage` and
`model_usage` are still read from each invocation's own transcript. Its
statusLine-sourced cost apportionment is removed, together with the API-duration
apportionment that shared its cursor.

## Context

acs shipped two Claude Code status-line scripts. `statusline.py` rendered the
prompt line (ticket, pipeline glyphs, cost). `subagent-statusline.py` rendered
the reflection subagents' rows. Since MAR-1, `statusline.py` also sampled
Claude Code's statusLine payload (`total_cost_usd`, `total_api_duration_ms`)
into a per-checkout log on every refresh. `cost_sampler.allocate_cost`
consumed that log at run finalize and apportioned the dollar and API-duration
deltas across roles by token share. That was acs's only source of real
dollar figures.

`/acs:setup` stopped offering the status line when it was cut to conventions
and CI. That left a hand-wired UI customisation as the only feed for a whole
metric family. The status line is the user's own Claude Code setting, and
acs's aim is to lean on native Claude Code features rather than install
itself into them.

## Decision

Remove the status line and everything that exists only to feed or consume it:

- `statusline.py`, `subagent-statusline.py` and `cost_sampler.py` are deleted,
  along with the statusLine payload probes in `claude_code_adapter.py`.
- A run entry records measured `tokens`, `role_usage` and `model_usage`, and no
  longer carries `cost_usd`, `cost_basis`, `cost_scope`, `excluded_cost_usd`,
  `api_duration_ms`, `api_duration_basis` or `api_duration_scope`.
- `compute_ticket_totals` and `metrics.json` keep invocations, working time and
  tokens, and drop the cost and API-duration sums and their counters.
- `/acs:usage` and `/acs:metrics` report tokens and wall-clock time, and no
  dollar figures.
- Completion reports end their Metrics line at tokens.

Dollars are not estimated from a price table instead: ADR-0082 retired acs's
own price table, and that decision stands.

## Consequences

**No dollar figures anywhere in acs.** A team that needs spend reads it where
Claude Code reports it: its own `/cost`, the console, or its usage exports.
Tokens remain measured per role and per model, so the relative cost of skills
and roles is still visible.

**Old state stays readable.** The step-state and metrics schemas tolerate
unknown keys. A run entry or `metrics.json` written before this change keeps
its cost fields, and nothing reads them. The result schema, which rejects
unknown keys, still accepts `cost_usd`, `cost_basis` and `api_duration_ms` so
an older coordinator's result validates, and ignores them, as it already did
`tokens`.

**A user who wired `statusLine` to an acs script** sees Claude Code report the
missing script. Removing that setting is the fix.
