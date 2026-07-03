# 0039 — The spec-simplicity gate is scoped to `create-spec-planner` only; no `create-spec-verifier` dimension or meta-check is added

**Status**: Accepted · **Date**: 2026-07-03

## Context

With the gate's placement (ADR 0037) and disposition (ADR 0038) decided, a
further question arose during design iteration (clarification **C-4** in
this ticket's `clarifications.json`): should `create-spec-verifier` also
gain a meta-check confirming the simplicity question was actually asked by
the planner, hardening the gate against a planner that silently skips the
evaluation?

## Decision

No. The gate is scoped exclusively to the `create-spec-planner` charter and
the coordinator's existing User-interaction path. `create-spec-verifier` is
not touched and keeps exactly its current four numbered dimensions —
`design-conformance`, `acceptance-coverage`, `completeness`, `consistency`
(`plugins/acs/agents/create-spec-verifier.md`). No fifth dimension, and no
"was the question asked?" meta-check, is added. The user's answer to
clarification C-4 was explicit: "planner charter only ... no create-spec
verifier change." This keeps the change minimal (no new subagent, state
file, hook, or `clarifications.json` schema change) and avoids re-opening
the Option B rejection from ADR 0037 through a side door.

## Alternatives considered

- **A `create-spec-verifier` meta-check ("was the simplicity question
  asked?").** Rejected per clarification C-4. Beyond user preference, this
  would also structurally strain the verifier's no-user constraint: the
  verifier can only emit blocking findings, so a meta-check failure would
  block the iteration over a *process* omission rather than a *substantive*
  spec defect — a different and unwanted failure mode from the rest of the
  verifier's dimensions, which all judge the finished spec set's content.

## Consequences

- `create-spec-verifier.md` is unmodified by this ticket. A regression test
  (`tests/acs/test_skill_contracts.py`,
  `TestSpecSimplicityGate.test_create_spec_verifier_still_four_dimensions`)
  pins the four-dimension count and asserts no "spec-simplicity"-style fifth
  dimension name appears, guarding against a future implementer adding one.
- `code-verifier` dimension 12 ("Simplicity & scope") is likewise unchanged
  in mechanism; the AC-7 deconfliction is recorded as a documentation clause
  in `docs/requirements/reflection.md` (spec-time/surfaced vs. code-time/
  blocking), not a behavior change to either verifier.
- Whether the planner actually performs the evaluation in practice (as
  opposed to whether the charter instructs it to) is behavioral quality —
  the agentic-e2e tier, not unit-testable — and is deliberately left
  unenforced by any blocking mechanism, consistent with the surface-only
  disposition in ADR 0038.
