# 0078 — Create-project remediation loop is execute → verify only; ADR-0004 amended

**Status**: Accepted · **Date**: 2026-08-24

## Context

MAR-301 changes `/acs:create-project`'s remediation loop from
plan-execute-verify-every-iteration to plan-once-then-execute-verify — the
same decision class ADR-0004's existing (pre-MAR-74) in-sentence text
already records for `/acs:code` (MAR-70/MAR-71/MAR-72), and the class
ADR-0077 already extended to `/acs:docs-sync` (MAR-300). `/acs:create-project`'s
verifier is already independently anchored: it re-runs the actual
build/lint/test/coverage-tooling commands and observes real exit codes rather
than trusting the planner's claims — so the per-iteration re-plan the
pre-MAR-301 topology spawned on iteration 2/3 was pure overhead: a mechanical
restatement of already-known failing commands the executor could receive
directly. Since MAR-74 (ADR-0073), ADR-0004 is append-only — amendments happen
via new ADR files, never in-place edits.

## Decision

`/acs:create-project`'s remediation loop is now **execute → verify only**: the
plan is authored exactly once per run, before the loop starts, and
iteration-2+ findings from the verifier route directly to the **executor**'s
`<task>` `<context>` — not to a new plan. This amends ADR-0004's `except
/acs:code` remediation-loop carve-out (already extended to `/acs:docs-sync`
by ADR-0077) to also name `/acs:create-project`.

Two clauses of ADR-0004 are explicitly **not** touched by this amendment:

- **The artifact-naming clause stays `/acs:code`-only.** Create-project does
  not rename its plan artifact to `plan.md`; it keeps
  `phases/create-project/iter-<n>-plan.md` (n always 1, written once, never
  rewritten on a later iteration).
- **ADR-0004's actual subject — verifier independence — is unchanged.**
  `create-project-verifier.md` is byte-unmodified this ticket, and the skill
  retains "The verifier MUST actually run, from `<checkout_root>`, the exact
  commands the plan pinned, and see them pass".

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- A `/acs:create-project` run that needs 3 iterations spawns exactly one
  planner subagent across the whole run; the iteration cap (max 3) and the
  fixed (non-lane-conditional) verify depth are unchanged.
- The create-project planner's charter narrows accordingly: it no longer
  carries a "route iteration >= 2 findings back into a new plan"
  responsibility — that responsibility moves to the executor's `<context>`
  handling, mirroring `/acs:code`'s MAR-71 shape and `/acs:docs-sync`'s
  MAR-300/ADR-0077 shape.
