# 0038 — The spec-simplicity gate surfaces found alternatives; it never blocks or auto-loops back to re-plan

**Status**: Accepted · **Date**: 2026-07-03

## Context

Once the spec-simplicity gate exists (ADR 0037), it must decide what happens
when it finds a materially simpler alternative decomposition. Two
dispositions were weighed:

- **Option A (chosen, ticket-mandated)** — SURFACE: a found alternative
  becomes a question to the user/spec owner; the user decides; the decision
  is ledgered via `clarify.py`; the run continues on the chosen direction.
- **Option B (rejected)** — BLOCK: the gate would force a simpler
  re-decomposition automatically when triggered (auto-loopback to re-plan).

"Materially simpler" is a judgment call with no single objectively correct
answer — a "simpler" decomposition can lose on non-functional grounds the
gate cannot see (team familiarity, planned follow-on work, external
constraints). MAR-3 (the closed predecessor to this ticket, PR #171) was
rejected in part because it raised a complexity concern as a hard gate at
the wrong authority and the wrong confidence level.

## Decision

The spec-simplicity gate only ever **surfaces** a found alternative as a
question to the user/spec owner for a **decision**. It never blocks the run
and never triggers an automatic re-plan/loopback. The chosen direction
(original approach or the simpler alternative) is what the executor builds
against, exactly as any other recorded clarification. This mirrors the
ticket's explicit AC-2 requirement ("surface, not implement-then-note") and
is enforced by wording alone: "surface" and "decision" framing is used
throughout the gate's description in `create-spec-planner.md` and
`SKILL.md`; "block", "loopback", and "auto-reject" framing is deliberately
absent from the gate's own description.

## Alternatives considered

- **Option B — BLOCK (auto-loopback to re-plan).** Rejected. Guarantees the
  simpler alternative is taken when found and removes any risk of a user
  rubber-stamping unnecessary complexity, but an automatic block would let
  the tool override a legitimate engineering decision the spec owner may
  have good reasons for. This re-introduces exactly the MAR-3 over-reach:
  raising a complexity concern as a hard gate at the wrong authority and the
  wrong confidence level. Because the "materially simpler" threshold is high
  and therefore inherently subjective, a false positive under BLOCK is far
  more costly (a stalled run) than under SURFACE (one extra question).

## Consequences

- A materially-simpler alternative that the user declines to take ships
  as-is; the gate does not force the "better" outcome — accepted, since the
  ticket's own AC-2 requires surface, not enforcement.
- A false positive (a non-material "simpler" alternative flagged) costs at
  most one wasted clarification question; it never blocks a run.
- Contract tests (`tests/acs/test_skill_contracts.py`,
  `TestSpecSimplicityGate`) assert "surface"/"decision" framing is present,
  and "block"/"loopback"/"auto-reject" framing (as the gate's own
  disposition) is absent, in the gate's own co-location window in both
  `create-spec-planner.md` and `SKILL.md` — window-scoped, not whole-file,
  since both files legitimately use "block" elsewhere for unrelated concerns
  (verifier findings, escalation, handoff).
- No auto-loopback path, new state, or schema field is introduced anywhere
  in the create-spec triad.
