# 0084 — Create-architecture/create-design/create-requirements remediation loops become execute → verify only, completing the plan-once migration; ADR-0004 amended

**Status**: Accepted · **Date**: 2026-08-30

## Context

`/acs:create-architecture`, `/acs:create-design`, and `/acs:create-requirements`
were the last three of the twelve triad-keeping skills still running the
original plan-execute-verify-every-iteration shape — the same decision class
ADR-0004's existing (pre-MAR-74) in-sentence text already records for
`/acs:code` (MAR-70/MAR-71/MAR-72), and that ADR-0077/0078/0079/0083 already
extended to `/acs:docs-sync`, `/acs:create-project`,
`/acs:standardize-project`, and the 5 bootstrap-doc skills
(`/acs:create-prd`/`-quality`/`-standards`/`-operations`/`-principles`)
respectively. Each of these three skills' verifiers is already independently
anchored — `create-architecture-verifier.md` re-derives HLD/LLD consistency
and PRD/codebase coverage itself; `create-design-verifier.md` re-runs its five
check dimensions fresh against the codebase and architecture docs;
`create-requirements-verifier.md` independently re-enumerates feature areas
and re-checks citations — so the per-iteration re-plan the prior topology
spawned on iteration 2/3 was pure overhead: a mechanical restatement of
findings the executor could receive directly. Notably, both
`create-design-executor.md` and `create-requirements-executor.md` already
accepted iteration-2+ verifier findings via their `<task>`'s `<context>` and
already carried a "fix every finding in `<context>`" charter step — that
capability simply went unused because their coordinators re-spawned a planner
first; only `create-architecture-executor.md` needed the same `<context>`
handling added. Since MAR-74 (ADR-0073), ADR-0004 is append-only — amendments
happen via new ADR files, never in-place edits.

## Decision

**(a) Execute → verify only, for all three skills.** Each of
`/acs:create-architecture`, `/acs:create-design`, and
`/acs:create-requirements`'s remediation loop is now **execute → verify
only**: the plan is authored exactly once per run, before the loop starts,
and iteration-2+ findings from the verifier route directly to the
**executor**'s `<task>` `<context>` — not to a new plan. This amends
ADR-0004's `except /acs:code` remediation-loop carve-out (already extended to
`/acs:docs-sync`, `/acs:create-project`, `/acs:standardize-project`, and the
5 bootstrap-doc skills by ADR-0077/0078/0079/0083) to also name these three,
completing the migration: **all twelve** triad-keeping skills now plan
exactly once per run.

**(b) Not touched by this amendment.** Two clauses stay exactly as
ADR-0077/78/79/83 already established them:

- **The artifact-naming clause stays `/acs:code`-only.** None of the three
  skills renames its plan artifact to `plan.md`; each keeps
  `phases/<skill>/iter-<n>-plan.md` (`n` always 1, written once, never
  rewritten on a later iteration).
- **ADR-0004's actual subject — verifier independence — is unchanged.** All
  three verifiers' independent re-derivation/re-check behavior (codebase and
  PRD spot-checks, HLD/LLD cross-referencing, feature-area re-enumeration and
  citation-sidecar verification) continues to re-derive ground truth from the
  repo and docs rather than anchoring on the planner's or executor's claims;
  none of the three `-verifier.md` files changed as part of this ticket.

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- A run of any of the three skills that needs 3 iterations spawns exactly one
  planner subagent across the whole run; the iteration cap (max 3) and the
  fixed (non-lane-conditional) verify depth are unchanged.
- Each of the three skills' planner charters narrows accordingly: none
  carries a "route iteration >= 2 findings back into a new plan"
  responsibility any longer — that responsibility moves to the executor's
  `<context>` handling, mirroring `/acs:code`'s MAR-71 shape and
  ADR-0077/78/79/83's own skills.
- `create-architecture-executor.md` gains the same `<context>`-driven
  "fix every finding, nothing beyond the plan" step
  `create-design-executor.md` and `create-requirements-executor.md` already
  had; the latter two agent files are otherwise unchanged.
- All three verifiers and their independent-corroboration behavior are
  unchanged by this ticket.
- No settings key, schema, state-file shape, or artifact-path change
  (zero-migration): each skill keeps its `iter-<n>-plan.md` name and its
  existing dimension names/numbers/order.
- Docs updated to reflect the completed migration: `docs/architecture/hld/c4-component.md`,
  `docs/architecture/hld/data-model.md`, `docs/architecture/lld/flows/hook-gated-skill-run.md`,
  `docs/product/roadmap.md`, and `docs/requirements/functional/reflection.md` no
  longer name any triad-keeping skill as an exception to the plan-once shape.
