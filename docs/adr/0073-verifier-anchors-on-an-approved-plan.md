# 0073 — Verifier anchors on an approved plan; ADR-0004 amended

**Status**: Accepted · **Date**: 2026-08-24

## Context

MAR-69 slice 4 wants `/acs:code`'s verifier to judge a changeset against the
plan artifact's own `## Executor tasks & file map` and `Approach` content —
something ADR 0004 explicitly forbids today ("never the same-iteration plan
… it consumes only the plan's verifier-checklist section, a floor never a
ceiling"). ADR 0004 names two hazards for that prohibition: a model
reviewing its own output rubber-stamps, and a verifier judging against the
same-iteration plan certifies plan-conformant-but-wrong work. Slice 3
(MAR-73, ADR 0076) already made the plan a deterministic-predicate-approved,
pre-loop artifact (`plan-approval.json`), which structurally dissolves both
hazards — this ADR amends ADR-0004's verifier-anchoring clause accordingly,
append-only (ADR-0004 itself is never edited).

**Evidence provenance.** This ADR records the decision as implemented by
this ticket's own change rather than as ratified against MAR-69's epic
design, because that `design.md` — cited by `ticket.json`'s description as
"design.md slice 4, decision D1-A" — was unreachable in this workspace this
session (no local workspace partition exists for MAR-69, and the GitHub API
was unavailable), so this decision could not be cross-checked against or
reconciled with the epic-level design; if that design fixes a different
framing for this decision, a future amendment should reconcile the two. This
mirrors the same disclosure ADR 0076 recorded for itself.

## Decision

1. **The plan becomes a legitimate anchor for one bounded new verifier
   dimension (15, Plan conformance) iff it carries a deterministic, non-LLM
   approval record** — `plan-approval.json`'s `eligible: true`, `plan_path
   == phases/code/plan.md`, and a `plan_sha256` matching the current
   `plan.md` bytes. Both hazards ADR-0004 named are structurally absent in
   this case:
   - *"A model reviewing its own output rubber-stamps"*: the approval is
     computed by a pure predicate over the plan's own bytes
     (`plan_approval_eligible`, digest computed inside the predicate),
     written by a script that is the sole writer (ADR 0076 D-1/D-2) — never
     by the verifier, the planner, or the coordinator.
   - *"A verifier judging against the same-iteration plan certifies
     plan-conformant-but-wrong work"*: since MAR-71 the plan is not a
     same-iteration artifact at all — it is authored once, before the loop,
     approved before any execute, and cannot be bent to match the code
     without the visible revocation path (below) producing a new digest and
     a new record.
2. **Dimension 1 stays the review loop's fixed point (ADR 0066), unchanged.**
   Dimension 15 is strictly subordinate to it and can never certify away a
   missed `ticket.acceptance_criteria` entry — an approved plan is never
   evidence that an AC is satisfied.
3. **This amends ADR-0004's verifier-anchoring clause** ("never the
   same-iteration plan … it consumes only the plan's verifier-checklist
   section, a floor never a ceiling"): the plan's `## Executor tasks & file
   map` and `Approach`/`API/data changes` content also become a bounded
   conformance contract for dimension 15 specifically, when — and only
   when — the approval record above holds; every other dimension, and every
   case where the record is absent or does not hold, is unaffected — the
   plan stays a floor, never a ceiling, everywhere else.
4. **The revocation path is the escape hatch.** When dimension 15 blocks
   because the *plan* is wrong rather than the changeset, `plan.md` is
   copied to `plan-superseded-<k>.md` (byte-identical, preserving existing
   `iter-<n>-verify.md` citations), revised in place, and re-approved via a
   fresh `plan-approval.py` run — reached only at an iteration/run boundary
   and only on an explicit, `clarify.py`-recorded user answer, never
   automatically.

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- The verifier now reads `plan-approval.json` as an input (a second reader,
  alongside `plan-approval.py`'s writer role); D-2's writer-only guard in
  `tests/acs/test_plan_approval.py` is narrowed accordingly — reading the
  record is not writing it.
- `plan-superseded-<k>.md` moves from reserved-but-inert to a real,
  written-and-read artifact; it is never itself an approval input or a
  conformance contract, by dimension 15's `plan_path` activation condition.
- Approval stays non-gating this release (ADR 0076 D-3): dimension 15 is a
  verifier *dimension*, not a `/acs:create-pr` gate change.
