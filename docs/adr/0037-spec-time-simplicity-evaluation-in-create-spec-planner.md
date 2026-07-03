# 0037 — Add a spec-time simplicity-evaluation step to the `create-spec-planner` charter, surfaced by the coordinator

**Status**: Accepted · **Date**: 2026-07-03

## Context

`/acs:create-spec` had no check for whether a decomposition was
over-engineered: it turned a ticket into implementation specs without ever
asking whether a *materially* simpler approach would meet the same
acceptance criteria. Over-complication, when it happened, was caught only by
`code-verifier` dimension 12 ("Simplicity & scope",
`plugins/acs/agents/code-verifier.md:106-110`) — after the code was already
written, the most expensive point to redirect. MAR-88 re-targets the closed
MAR-3 ("Think Before Coding" flag in `/acs:code`, PR #171), rejected because
`/acs:code` already plans before coding and already blocks post-hoc on
over-complication — the wrong place and the wrong time.

Three placements were weighed for where the spec-time check should live:

- **Option A (chosen)** — the `create-spec-planner` evaluates the
  decomposition for a materially simpler alternative while it decomposes, and
  records a found alternative through its existing ambiguity-surfacing seam;
  the coordinator surfaces it to the user through its existing
  User-interaction path.
- **Option B (rejected)** — a new `create-spec-verifier` dimension mirroring
  `code-verifier` dimension 12.
- **Option C (rejected, runner-up)** — the coordinator re-evaluates
  decomposition simplicity independently, without any planner charter
  change.

## Decision

Adopt Option A. The `create-spec-planner`'s existing decompose step
(`plugins/acs/agents/create-spec-planner.md`, charter step 4) gains one
additional analysis clause: while deciding how to decompose the ticket,
evaluate whether a **materially** simpler decomposition would satisfy the
**same acceptance criteria** with materially less code/complexity. This is
not a new charter step or a new analysis pass — it is folded into reasoning
the planner already performs, at zero extra subagent spawn or iteration
cost.

If the evaluation finds such an alternative, the planner records it using
the charter's existing ambiguity-surfacing seam ("Flag genuine ambiguities …
as explicit questions", charter step 1) — writing to the plan artifact's
`## Open questions` heading and the `<questions>` element of its `<result>`.
The coordinator (`plugins/acs/skills/create-spec/SKILL.md`) picks the
question up through its existing User-interaction step, which already
groups all open questions into one interaction and records each answer as
its own `clarify.py` ledger entry. No new mechanism, schema, subagent, state
file, or hook is introduced.

## Alternatives considered

- **Option B — new `create-spec-verifier` dimension.** Rejected: the
  `create-spec-verifier` only runs *after* the full spec set is written —
  this is implement-then-note at spec level, exactly what the before-the-gate
  requirement forbids. Worse, the verifier structurally has no user
  (`create-spec-verifier.md:120-121`: "You do not use `needs_input`: you
  have no user"), so a verifier dimension can only ever emit a blocking
  finding, never surface a question for a decision — directly violating the
  surface-not-block mandate (ADR 0038). It would also collide in name and
  shape with `code-verifier` dimension 12, muddying the spec-time/code-time
  deconfliction.
- **Option C — coordinator-only re-evaluation.** Not disqualified on
  correctness, but the coordinator would have to re-derive the same
  decomposition analysis the planner just performed — duplicated reasoning
  and higher token cost than Option A, and it blurs the plan/coordinate
  separation the reflection model relies on (the planner analyzes, the
  coordinator orchestrates and talks to the user). Option A already gets the
  surfacing half of this option for free, so C is strictly dominated.

## Consequences

- `plugins/acs/agents/create-spec-planner.md` gains one analysis clause in
  its decompose step; no new charter step, seam, field, or subagent.
- `plugins/acs/skills/create-spec/SKILL.md` gains one documenting sentence
  in its Plan-phase section noting the planner may surface this question
  type; the existing User-interaction mechanism is unchanged.
- No new message schema: the simplicity alternative is one more entry in the
  existing `<questions>` list and `## Open questions` heading.
- Fires before any spec file is written, satisfying the before-the-gate
  requirement exactly, since the evaluation is part of the plan phase.
- The planner both proposes the decomposition and critiques it — a degree of
  self-review — mitigated because the `create-spec-verifier` still judges
  the final spec set fresh and independently, and the surfaced decision is
  owned by the user, not the planner.
