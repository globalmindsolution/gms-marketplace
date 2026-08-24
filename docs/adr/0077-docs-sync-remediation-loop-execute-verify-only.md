# 0077 — Docs-sync remediation loop is execute → verify only; ADR-0004 amended

**Status**: Accepted · **Date**: 2026-08-24

## Context

MAR-300 changes `/acs:docs-sync`'s remediation loop from
plan-execute-verify-every-iteration to plan-once-then-execute-verify — the
same decision class ADR-0004's existing (pre-MAR-74) in-sentence text
already records for `/acs:code` (MAR-70/MAR-71/MAR-72): the plan is authored
once, before the loop, and iteration-2+ findings are remediated without a
new plan. `/acs:docs-sync`'s verifier is already independently re-derived —
it never trusted the planner's doc-delta list as authoritative in the first
place — so the per-iteration re-plan the pre-MAR-300 topology spawned on
iteration 2/3 was pure overhead: a mechanical restatement of findings the
executor can receive directly. Since MAR-74 (ADR-0073), ADR-0004 is
append-only — amendments happen via new ADR files, never in-place edits.

## Decision

`/acs:docs-sync`'s remediation loop is now **execute → verify only**: the
plan is authored exactly once per run, before the loop starts, and
iteration-2+ findings from the verifier route directly to the **executor**'s
`<task>` `<context>` — not to a new plan. This amends ADR-0004's `except
/acs:code` remediation-loop carve-out to also name `/acs:docs-sync`.

Two clauses of ADR-0004 are explicitly **not** touched by this amendment:

- **The artifact-naming clause stays `/acs:code`-only.** Docs-sync does not
  rename its plan artifact to `plan.md`; it keeps
  `phases/docs-sync/iter-<n>-plan.md` (n always 1, written once, never
  rewritten on a later iteration).
- **ADR-0004's actual subject — verifier independence — is unchanged.**
  `docs-sync-verifier.md` is byte-unmodified this ticket, and it continues to
  re-derive doc impact itself from the diff and upstream artifacts rather
  than anchoring on the planner's output.

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- A `/acs:docs-sync` run that needs 3 iterations spawns exactly one planner
  subagent across the whole run; the iteration cap (max 3) and the fixed
  (non-lane-conditional) verify depth are unchanged.
- The docs-sync planner's charter narrows accordingly: it no longer carries
  a "route iteration >= 2 findings back into a new plan" responsibility —
  that responsibility moves to the executor's `<context>` handling, mirroring
  `/acs:code`'s MAR-71 shape.
