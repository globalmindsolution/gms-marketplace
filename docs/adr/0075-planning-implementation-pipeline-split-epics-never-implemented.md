# 0075 — The acs pipeline splits into a planning phase (`create-ticket(epic) → create-design → fan-out`) and an implementation phase (`create-ticket → code → … → merge-pr`); epics are never implemented

**Status**: Accepted · **Date**: 2026-08-20

## Context

Before this decision, an epic's own `/acs:create-ticket` run did three
things in one invocation: created the epic, decomposed it into children, and
minted them via `new-ticket.py` — all before the epic's own `/create-design`
had ever run. `/acs:code` could also, in principle, be invoked directly on
an epic ticket, even though an epic is a grouping/tracking record with no
implementation of its own.

This conflated two genuinely different kinds of work under one skill
surface: **planning** (deciding what an epic breaks down into, informed by
its approved architecture) and **implementation** (writing code against a
concrete, PR-sized ticket). Fanning out before design meant the child
breakdown could not be informed by the design's own slice/seam analysis, and
nothing in the pipeline stopped `/acs:code` from being pointed at an epic
directly.

This decision was implemented across three slices of MAR-69 (the epic this
ADR itself is a child of): MAR-75 (`gate_code` refuses `type == "epic"`
outright), MAR-77 (`create-design` reclassified from a workflow skill to a
`PLANNING_SKILLS`-registered skill, decoupled from `WORKFLOW_SKILLS`), and
MAR-78 (`/acs:create-ticket <epic-id> --fan-out`, a second invocation mode
that mints an existing, already-designed epic's children — replacing the
old unconditional Step 4 that ran during the epic's own creation).

## Decision

1. The acs pipeline is now two phases for an epic, not one:
   - **Planning phase**: `create-ticket(epic)` (creates the epic with
     `children: []`) → `create-design` (approves the epic's `design.md`) →
     `create-ticket <epic-id> --fan-out` (mints children from the design's
     slices, Step-2 gate reused) → STOP.
   - **Implementation phase**, run independently per child:
     `create-ticket` (the child, minted by fan-out) → `code` → `docs-sync`
     → `create-pr` → `merge-pr`.
2. **Epics are never implemented directly.** `gate_code` refuses any ticket
   with `type == "epic"`; the only path from an epic to running code is
   fanning it out and implementing a child.
3. `create-design` is registered as a **planning skill**
   (`acs_lib.PLANNING_SKILLS`), not a workflow skill — it sits in the
   planning phase, not the implementation phase, though every hooked
   consumer (dispatch, skill-start, clarify, metrics, handoff) keeps routing
   it exactly as before.

## Consequences

**Positive:** a child's breakdown can now be genuinely informed by the
epic's approved design (slice/seam content), rather than being proposed
before any design exists. An epic ticket can no longer silently attempt
implementation — refusal is explicit and points to the remediation path
(approve a design, then fan out, then implement a child). The planning/
implementation split gives each phase its own, uncontended entry point
instead of overloading one invocation of `/acs:create-ticket` with three
different responsibilities.

**Accepted cost:** an epic now requires two explicit `/acs:create-ticket`
invocations (creation, then `--fan-out`) instead of one, with
`/create-design` run in between — the old single-invocation, fan-out-at-
creation shape (D-4/D-6 in this ADR's design) is retired. Existing epics
created before this decision landed with children already minted are
unaffected retroactively; only epics created (or fanned out) after all
three implementing slices are live follow the new shape.

**Verification note:** this decision's three clauses ship across three
separate slices of the same epic (MAR-75, MAR-77, MAR-78); no single
pre-merge tree contains all three simultaneously; that is a property of how
the epic's slices were sequenced and reviewed, not of the decision itself,
which is settled and accepted as a whole once the three slices land.
