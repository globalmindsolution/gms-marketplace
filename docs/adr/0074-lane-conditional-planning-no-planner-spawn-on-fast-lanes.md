# 0074 — Lane-conditional planning: no `code-planner` spawn on TRIVIAL/SMALL; coordinator authors `plan.md` itself

**Status**: Accepted · **Date**: 2026-08-23

## Context

MAR-58 (ADR 0034) made verify depth lane-driven but left the Plan step
unconditional: every `/acs:code` run, on every lane, spawns exactly one
`acs:code-planner` subagent before the loop (MAR-71, slice 1b of MAR-69).
For TRIVIAL/SMALL tickets — already capped at a single execute→verify
iteration by ADR-0034 — that planner spawn is a fixed cost (a full subagent
context window) buying comparatively little: the fold's five-section spec
content and the six required headings are the same regardless of lane, and a
TRIVIAL/SMALL surface rarely needs a dedicated repo-survey pass to produce
them.

Four `code-verifier` inputs consume the plan artifact and are live even at
light depth — dimension 1's completeness/structure sub-checks, dimension 8
(Architecture), dimension 9 (System design), and dimension 13
(Audience-style, BLOCKING) — so dropping the plan artifact on fast lanes
would regress G16 (no defect-catch regression). The artifact must survive;
only its author may change.

## Decision

1. **D-1 — the coordinator-authored `plan.md` is byte-for-byte the same
   contract, a different author.** On TRIVIAL/SMALL, the coordinator writes
   `<partition>/phases/code/plan.md` itself at the Plan step: the same six
   required headings (`## Spec analysis`, `## Executor tasks & file map`,
   `## Test strategy`, `## Documentation map`, `## Risks`, `## Verifier
   checklist`), the same five fold section literals in the same order when
   the fold is active, both mandatory verbatim clauses, and an explicit
   intake-mode statement. "Minimal" names the authorship shortcut only — the
   coordinator skips spawning a separate subagent — never a content shortcut:
   every section must stay substantive, never empty, a placeholder, or "see
   ticket", because the verifier's completeness sub-check judges this
   artifact identically regardless of who wrote it.
2. **D-2 — the lane source is the freshly recomputed lane.** The spawn/no-spawn
   decision is made once, at the Plan step, from `derive_lane(ticket.size,
   ticket.stakes, ticket.needs_design, ticket.type)` recomputed fresh, exactly
   as the Start step already does — never from the cached `ticket.lane`,
   which can be stale or hand-edited.
3. **D-3 — mid-flight escalation never retro-spawns a planner.** A TRIVIAL/
   SMALL run that escalates to STANDARD/COMPLEX mid-flight raises the verify
   depth and the iteration ceiling only, monotonically. No planner is spawned
   after the fact, and the coordinator-authored `plan.md` remains the plan
   artifact for the rest of the run, because it already satisfies the same
   contract. The symmetric user-confirmed de-escalation likewise never
   revokes an already-authored plan.
4. **D-4 — no plan XML message on the fast lanes.** Because no planner
   subagent is spawned on TRIVIAL/SMALL, no `<task phase="plan">` message is
   sent and no `<result>` is returned; there is nothing to validate against
   the XSD and no `iter-<n>-plan.xml` snapshot to persist. `plan.md` is the
   durable record on every lane, and the resume path is unchanged because it
   keys on the presence of `plan.md`, not on who wrote it.
5. **D-5 — honest G14 scoping.** The saving this decision delivers is exactly
   one `acs:code-planner` subagent spawn and its context window per fast-lane
   run — on lanes that have already capped at **1** iteration since ADR-0034
   (`docs/adr/0034-light-verify-one-iteration-cap.md`). It is **not** a
   wholesale ≥ 60% wall-clock/token reduction; `prd.md`'s G14 metric ("reduced
   **≥ 60%**") is intent under the executor's factual-vs-intent boundary and
   is neither rewritten nor claimed met by this decision.

## Alternatives considered

- **Drop the plan artifact entirely on fast lanes.** Rejected: regresses G16
  — dimensions 1, 8, 9, and 13 would have no input to judge, and the executor
  and `/acs:test --for-ticket` would lose their file-map/test-strategy
  source.
- **Keep the planner subagent spawn on every lane.** Rejected: no saving at
  all; this is the status quo MAR-72 exists to narrow.
- **A machine-generated template plan on fast lanes (no coordinator
  judgment).** Rejected: dimensions 8/9/13 need actual judgment
  (Approach/API-data-changes content, audience-style register) that a fixed
  template cannot honestly supply; a template would either be too generic to
  pass dimension 13 or would need per-ticket judgment anyway, at which point
  it is simply the coordinator authoring the plan.

## Consequences

- **G14 scoped honestly (D-5).** The metric this decision moves is "one
  planner subagent spawn removed per fast-lane run", not a wall-clock/token
  percentage; `prd.md`'s G14 line and its **≥ 60%** figure are unchanged by
  this ticket.
- **G16 preserved.** All four plan-dependent verifier inputs (dimension 1
  completeness/structure, dimension 8 Architecture, dimension 9 System
  design, dimension 13 Audience-style) keep a valid target on TRIVIAL/SMALL;
  the verifier still runs in every lane and the TDD/coverage gate is
  untouched.
- No settings key, no `settings.schema.json` change, no `acs-messages.xsd`
  change, no state-file shape change, and no Python production change — this
  decision is prose-only in `code/SKILL.md`, `code-planner.md`, and
  `code-verifier.md`.
- `docs/adr/0034-light-verify-one-iteration-cap.md` is amended to narrow its
  planner-spawn consequence to STANDARD/COMPLEX only; its iteration caps
  (light = 1, full = 3) are unchanged.
- `docs/requirements/functional/reflection.md` records `/acs:code` as a
  conditional triad-keeping skill going forward.
