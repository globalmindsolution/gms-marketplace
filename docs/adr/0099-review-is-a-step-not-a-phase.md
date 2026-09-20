# 0099 — The changeset review is a step of its own; the multi-lens rule relocates to `/acs:review-code`

**Status**: Accepted · **Date**: 2026-09-20

**Supersedes**: [0067](0067-code-verifier-multi-lens-adversarial-rigor-upgrade.md)

**Related**: [0004](0004-reflection-with-independent-verifier.md) (the
verifier is independent — this ADR takes that further: independent of the
skill, not only of the executor), [0096](0096-workflow-is-a-list-not-a-graph.md)

## Context

ADR-0067 gave the full-depth `/acs:code` verifier four parallel lenses over
the same diff and an adversarial merge pass before findings counted. The
mechanism was right. Where it sat was not.

**The implementer graded its own output.** `/acs:code` planned (until
ADR-0092), implemented, and then verified. A skill that decides when it is
done is a skill with an interest in the answer, and the iteration ceiling —
how many rounds of judgement a change gets — was a property of the
*implementation* leg rather than of the review.

**Only one of four delivery paths got the rigor.** ADR-0067 scoped the lenses
to `verify_depth == "full"` to protect the cheap paths' efficiency. After
ADR-0095 that became: `complex` got four lenses and an adversarial merge;
`standard` got one pass; `trivial` and `small` got one shallower pass. So
per-finding adjudication — the part that stops a lens's speculation from
counting as a defect — was a luxury reserved for the runs least likely to
need it, because a small change with a real bug is still a real bug.

**The full unit suite ran inside a discardable iteration.** The verifier ran
it every round, including rounds whose changes were about to be replaced by
the next round's. On a repo with a large instrumented suite that is the
single largest cost in the loop, spent repeatedly on a tree that was about to
change.

**"Confidence-scoring" named a mechanism that never existed.** ADR-0067's
merge pass was described that way in three live documents; there was no
0-100 scale, no threshold and no numeric value anywhere in acs. The
adversarial half was real; the scoring half was a phrase.

## Decision

**The review is `/acs:review-code`, a step of `ship.yaml`, and every delivery
path gets it.** `/acs:code` writes the change and stops: it has no verifier,
it does not judge the changeset, and it does not run the full suite.

**Five read-only lenses run in parallel** over the changeset, each reading a
distinct evidence source. Lens E blocks on the change's own documentation as
well as its correctness.

**Each candidate finding goes to ONE fresh-context adjudicator**, prompted to
refute it. The agent that judges a finding is never the agent that raised it,
and it arrives without the lens's reasoning — which is what makes the
refutation real rather than a re-read. This replaces ADR-0067's merge pass
and its "confidence-scoring" description; corroboration-by-count is gone with
it, because two lenses agreeing is not evidence when both read the same diff.

**A final gate runs the build, the lint, the full unit suite and coverage —
once, last.** This is the ONLY place the full suite runs in the pipeline. It
runs after the reading dimensions have had their say, because an iteration
already blocked by a finding does not need a suite run to say so and the tree
it would measure is about to change.

**Blocking findings re-enter at `code` through the workflow's single loop**
(`from: review-code`, `back_to: code`, `max_iterations: 3`,
`on_exhausted: fail`). A fourth round FAILS the run rather than passing it
with findings. The ceiling is the workflow's, not the leg's, because it
counts rounds of *judgement*.

**No planner runs between the review and the fix.** A finding already says
what is wrong and what would make it right, and carries a `resolved_when`; a
planning pass would spend a round restating the verdict. When a finding
genuinely invalidates the plan, the remedy is to fail the step with a summary
naming the plan as superseded (ADR-0098), not a planner inside the loop.

**A finding may be `disputed`, once.** The executor returns the evidence that
defeats the claim, the next adjudicator receives the dispute and rules again,
and a finding disputed then confirmed a second time stops the run for a human
rather than spending the last iteration on the same argument.

**Gone with the carve-out:** the verifier inside `/acs:code`,
`agents/code-verifier.md`, the legs' per-path verifier shape and iteration
ceiling — all review properties, so they leave with the review — and the
`post_code_test` settings block.

## Consequences

**Every change gets adjudicated findings, not just the complex ones.** The
rigor that ADR-0067 could only afford on one path is affordable on all four
now that it is one step running once, rather than a shape each leg carries.

**The full suite runs once per review round instead of once per verifier
pass**, and never inside an iteration that is about to be discarded.

**`/acs:code` and `/acs:review-code` work independently.** Either can be run
by hand on a subject: `/acs:code` implements, `/acs:review-code` reviews
whatever changeset exists. The loop between them is the workflow's, so
neither needs the other to be useful.

**What this gives up:** a run costs one more step boundary and one more
partition. That is the price of the agent that judges a change not being the
agent that wrote it — which is what ADR-0004 asked for and what a verifier
living inside the implementing skill could only approximate.

**`/acs:create-pr`'s brake moves with the verdict:** it refuses a run whose
recorded `/acs:review-code` step left `verifier_passed != true`, where it
previously read `/acs:code`'s.
