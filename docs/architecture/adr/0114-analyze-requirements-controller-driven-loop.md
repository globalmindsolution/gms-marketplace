# 0114 — analyze-requirements runs on a controller, not on prose

**Status**: Accepted · **Date**: 2026-09-30

**Builds on**: [0092](0092-skill-machinery-declared-per-skill.md) (no planner
role when the deliverable is the analysis — unchanged here).

## Context

`/acs:analyze-requirements` is gated at its edges and enforced by hooks:
`acs step start` / `step finish`, the executor file-map guard, SubagentStop
validation of every returned `<result>`, and the post-hook's derived fields.
Everything BETWEEN those edges is prose. SKILL.md tells the coordinator which
pass runs next (survey, synthesis, draft, review), when to slice, how to join
the judges' findings, when the cap of 3 is spent and when to publish; the
coordinator decides each of those itself. The kernel's own rule — derived,
never asserted — stops at the verdict: the loop's position is whatever the
coordinator believes it is.

Three concrete gaps follow from that:

- **Nothing notices a loop that has stopped converging.** A reviewer that
  returns the same blocking findings on iteration 2 as on iteration 1 gets a
  third draft pass anyway, which spends an iteration to learn nothing.
- **Publication is a prose `cp` and `git add`.** The file-map guard stops a
  subagent writing to the ticket's docs folder; nothing checks that the
  coordinator's copy is the reviewed bytes, or that it committed only the
  docs folder.
- **One analyst answers two questions.** The survey pass records both what
  the ticket asks (requirements, open questions) and what code it touches
  (impact). The impact half is the one the reviewer re-derives from the
  repository, and the one that parallelises by code area.

A comparable skill built outside acs — a controller that owns durable state
and hands the skill exactly one action at a time — showed each of these gaps
closed without losing the reflection loop.

## Decision

1. **A controller owns the loop.** `acs.py analysis next` prints exactly one
   action; the coordinator performs it, then reports it with the matching
   `acs.py analysis record-*` verb. The controller never dispatches an agent,
   and the coordinator never advances the loop on its own reading. State lives
   in `steps/analyze-requirements/loop.json`, written only by the controller.

   Actions: `plan` (the coordinator declares the code areas once) → `survey`
   (the requirements lane plus one impact lane per code area, dispatched in
   one message) → `synthesize` → `clarify` → `draft` → `review` ⇄ `draft` →
   `publish` → `completed`, plus `blocked` and `failed`. `synthesize` always
   runs: the requirements lane and at least one impact lane are always two.

2. **The controller derives, the coordinator reports.** `record-review` reads
   the three judge slices' `<result>` snapshots itself: the iteration passes
   only when every slice completed with no blocking finding. The coordinator
   passes no verdict.

3. **Stall detection.** A blocking-finding set identical to the previous
   iteration's (same dimension, file and text, order-insensitive) ends the run
   `failed` with `stop_reason` `stalled`, without another draft pass. The cap
   stays 3 and counts draft → review cycles, not lanes.

4. **Failures that are not review findings block instead of retrying.** A
   malformed or missing `<result>`, a missing artifact, or an agent reporting
   `needs_input` makes `next` return `blocked` with the reason. No iteration is
   spent on a defect in the machinery. The one exception is a question still
   open after clarification: the existing not-ready-for-planning procedure
   publishes that analysis with `ready_for_planning: false`, so the loop
   drafts, reviews and publishes it, and `next` then returns `blocked`
   (`needs_input`) instead of `completed`.

5. **Publication is a script.** `acs.py analysis publish` refuses unless the
   last review passed on the exact draft bytes (hashed at review), refuses on
   the default branch or a detached HEAD (acs never commits to the default
   branch), runs the two deterministic checks (a finding fails the iteration
   like a reviewer's), copies the reviewed draft byte-for-byte to the
   ticket's docs folder, verifies the bytes, and commits the ticket's docs
   folder only. It never pushes. Nothing is written to the repository before
   this step.

6. **The code-impact survey gets its own agent.**
   `acs:analyze-requirements-impact-analyst` maps what code the ticket
   touches, one instance per code area. `acs:analyze-requirements-analyst`
   keeps the requirements lane, the synthesis (merging the lanes) and the
   draft. The impact reviewer is unchanged: it still re-derives the impact
   map fresh.

## Not decided here

**Keying the analysis by requirement area instead of by ticket**, so the next
ticket over the same code reuses it. Every downstream skill
(`create-impl-plan`, `create-api-contract`, `create-test-docs`) reads
`docs/tickets/<id>/analysis.md` by ticket; changing the key is a change to
all of them and gets its own ADR.

## Consequences

- The loop's position is inspectable (`acs.py analysis next` is read-only)
  and testable without a model: each transition has a unit test.
- The ordering, the cap, stall detection, the pass rule and the joining of
  notes and reviewer reports move into code; SKILL.md now describes what each
  action means. It did not get shorter (748 lines against 739): the prose the
  code replaced became the per-action instructions.
- De-duplicating findings across judge slices is now exact-match only, done by
  the controller; the coordinator's judgement-based merge is gone.
- A host that does not fire SubagentStop still works: the coordinator writes
  the `<result>` snapshot itself, as today, and the controller reads it.
- One more agent file, model-tier row and routing entry to maintain.
