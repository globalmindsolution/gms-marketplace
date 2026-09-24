# 0104 — No usage dashboards, no usage recording

**Status**: Accepted · **Date**: 2026-09-23

**Supersedes**: [0082](0082-session-anchored-transcript-measurement-statusline-cost-apportionment.md)
(its transcript measurement, the half [0103](0103-no-status-line-no-cost-metering.md)
kept), and the dashboard decisions [0013](0013-metrics-derives-panels-from-artifacts.md),
[0014](0014-metrics-helper-emits-json-skill-renders.md),
[0015](0015-metrics-single-show-widget-call.md),
[0016](0016-metrics-bounded-single-pass-walk.md),
[0017](0017-metrics-deterministic-cross-surface-rendering.md) and
[0019](0019-split-acs-metrics-into-pm-and-usage-skills.md).
**Amends**: [0103](0103-no-status-line-no-cost-metering.md) (it said tokens
stay measured; they no longer are) and
[0020](0020-ticket-due-date-and-deadline-panel.md) (its deadline panel is gone;
the `due_date` ticket field stays).

## Context

`/acs:metrics` and `/acs:usage` rendered delivery and usage dashboards from
state that every step wrote for them:

- `metrics.json`: ticket counts, PR counts and repo-level run, time and
  token totals;
- per-invocation `tokens`, `role_usage` and `model_usage`, measured at
  finalize by reading the session's transcript (`usage_reader.py`), which
  needed a session-correlation marker written by the pre-hook;
- the `run.json` `totals` placeholder.

Once the two dashboards are gone, nothing in acs reads any of this. The token
measurement was also broken in practice: no step start passed the session
marker to the invocation, so live runs recorded zero tokens.

## Decision

Remove both skills and everything that existed only to feed them:

- `skills/metrics/` and `skills/usage/`; the `metrics_aggregate*.py` and
  `metrics_render*.py` scripts; `usage_reader.py`;
- `acs_lib/metrics.py` (`update_metrics`, `compute_ticket_totals`,
  `backfill_distinct_pr_count`, `_measure_run_usage`, `elapsed_seconds`,
  `run_seconds`), `metrics.json` and `metrics.schema.json`;
- the session-correlation marker (`record_session_marker`,
  `accepted_session_marker`, `sessions/<ckid>/session.json`) and
  `append_invocation`'s `session` argument;
- the transcript-shape sections of `claude_code_adapter.py`, and its
  degradation switch, whose only callers measured usage;
- `PIPELINE_STEP_ORDER` (the funnel's column order) and
  `ATTRIBUTION_SKILL_MAP` (the transcript attribution override);
- `run.json`'s `totals`, and the token figure in every completion report's
  Metrics line.

A step still records what the pipeline itself needs: its status, timestamps,
stop reason, guard events, findings, errors and `states`.

## Consequences

**acs reports no usage.** Tokens, spend and time per ticket are Claude Code's
to report (`/cost`, the console, usage exports). acs's own ledger is the
workflow: run and step state, the tickets index and the PR it opened.

**Old state stays readable.** A `metrics.json`, a `session.json` or an
invocation's `tokens` written earlier is ignored. The step-state schema
tolerates unknown keys. The result schema still accepts the legacy usage
fields (`tokens`, `role_usage`, `model_usage`, `cost_usd`, `cost_basis`,
`api_duration_ms`) and ignores them, so an older coordinator's result still
validates.

**Gate evidence is unaffected.** `hostgates`' evidence file is how acs tells
whether its hooks fire at all. It was deliberately separate from the
correlation marker, and it stays.
