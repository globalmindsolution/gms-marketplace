# 0066 — Supersedes ADR 0006: fold spec-authoring into `/code`'s plan phase for every lane; `ticket.json`'s `acceptance_criteria`/DoD becomes the review loop's fixed point

**Status**: Accepted · **Date**: 2026-07-29

## Context

ADR 0006 (`docs/adr/0006-spec-plan-altitude-split.md`) kept `/acs:create-spec`
and `/acs:code`'s plan phase at fixed altitudes specifically so the review
loop would have an "immovable yardstick": the spec set is authored
interactively, gated, and stable across code-verifier iterations, while the
plan is rewritten each remediation pass. That reasoning was sound for the
mechanism that existed at the time — a separately-authored spec artifact was
the only thing in the pipeline that a headless remediation loop could not
silently rewrite out from under itself.

Two things were already true before this ticket shipped, though: `/code`'s
reflection loop never rewrites `ticket.acceptance_criteria` during escalation
(only `size`/`stakes`/`lane` escalate — MAR-107/MAR-108's guard-axes
contract), and code-verifier's Features dimension already judges the
changeset against `acceptance_criteria` independently of the spec set. The
ticket already carried a de facto second fixed point. ADR 0006's
"immovable yardstick" property is achievable without a separately-authored
spec artifact once the verifier is contractually required to always re-read
`ticket.json` fresh, every iteration, rather than trust the current
iteration's plan restatement.

## Decision

1. `/acs:create-spec` is deleted outright — its skill file, 3 agent files,
   both hook scripts, and its `GATES`/`WORKFLOW_SKILLS` registry entries no
   longer exist.
2. `/acs:code`'s planner self-authors the five-section fold content (Scope,
   Approach, API/data changes, Test plan, Out of scope) on EVERY lane when
   `<partition>/specs/` is absent or empty, and reads pre-existing specs
   unchanged when they are present (backward-compat with tickets minted
   before this ADR).
3. The code-verifier's review-loop fixed point relocates to
   `<partition>/ticket.json`'s `acceptance_criteria`/DoD, re-read fresh every
   verify iteration via the new "Acceptance-criteria conformance" dimension —
   never trusting the current iteration's plan-artifact restatement.
4. create-spec-verifier's other five dimensions are re-homed into
   code-verifier: design-conformance folds into the existing Architecture and
   System-design dimensions (no new dimension number); completeness and
   structure become sub-checks of the new dimension 1 (no new number);
   consistency is retired outright, with a stated reason (see Consequences);
   audience-style becomes a new, standalone, blocking dimension 13.

## Consequences

**Accepted cost:** STANDARD/COMPLEX tickets no longer get a dedicated,
pre-code, 3-iteration reflection loop for spec content — a wrong folded plan
is now caught only after code is written, in `/code`'s own single verify
pass. This is the direct cost of folding spec authoring into `/code`
universally, and the central risk ADR 0006 was originally protecting
against; it is accepted, not silently absorbed, because the review loop's
substantive AC/DoD fixed point (Decision 3) reproduces the property ADR 0006
actually needed — an immovable yardstick — without requiring a
separately-authored artifact to hold it.

**Positive consequence:** one fewer skill surface, one fewer agent-file set;
`gate_code` loses its whole STANDARD/COMPLEX create-spec precondition
branch. No shared-reference agent file is left behind by the deletion —
every one of create-spec's three agent files existed only for create-spec
itself.

**Retired, not silently dropped:** create-spec-verifier's `consistency`
dimension checked agreement across multiple independently authored spec
files (clashing schemas, unrealizable dependency order, `NN-` sequence
gaps). A single folded plan artifact — or a changeset judged as one coherent
unit — has no cross-file surface left to be inconsistent with, so this
dimension is retired outright rather than re-homed.

## Supersession

Supersedes ADR 0006 (`docs/adr/0006-spec-plan-altitude-split.md`). ADR
0006's original reasoning was sound for the mechanism that existed at the
time — `docs/adr/0006` is Accepted/relocated, not wrong. This ADR documents
why a different mechanism now achieves the same underlying guarantee (an
immovable review-loop yardstick) without a separately-authored spec
artifact.

## Amendment — MAR-72

**Date**: 2026-08-23 · **Status**: Accepted (narrowed)

`/acs:code`'s plan phase becomes lane-conditional (MAR-72, slice 2 of
MAR-69, ADR 0074 —
`docs/adr/0074-lane-conditional-planning-no-planner-spawn-on-fast-lanes.md`):
on STANDARD/COMPLEX a `code-planner` subagent is spawned as before; on
TRIVIAL/SMALL the coordinator authors `plan.md` itself, with zero planner
spawns. This narrows Decision 2's attribution to its plan's-author form,
without changing the fold's substance:

- **What narrows**: Decision 2's "`/acs:code`'s planner" becomes **the
  plan's author** — the `code-planner` on STANDARD/COMPLEX, the coordinator
  on TRIVIAL/SMALL (`plugins/acs/skills/code/SKILL.md:376`: "the plan's
  author (the code-planner on STANDARD/COMPLEX, the coordinator on
  TRIVIAL/SMALL, MAR-72)").
- **What does NOT narrow**: the fold's activation is still **every lane**
  and still unconditional — the trigger (`<partition>/specs/` absent or
  empty), the five sections (Scope, Approach, API/data changes, Test plan,
  Out of scope), and the read-pre-existing-specs backward-compat clause are
  all unchanged. Only *who writes it* changes.
- **Decisions 1, 3 and 4 are untouched** by this amendment — create-spec's
  deletion, the `ticket.json` `acceptance_criteria`/DoD fixed point, and the
  re-homed create-spec-verifier dimensions all stand as originally decided,
  and this ADR's Supersession of ADR 0006 above is unaffected.
