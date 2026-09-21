# 0095 — The delivery path is classified once from the plan and declared in ship.yaml; the dynamic lane machinery is retired

**Status**: Accepted — amended by [0098](0098-delivery-path-recorded-on-the-plan.md) (the plan judges the path and records it; `/acs:ship` and the `delivery:` block do not) · **Date**: 2026-09-17

**Supersedes**: [0030](0030-four-lane-hybrid-routing-from-size-stakes-axes.md),
[0031](0031-axes-authoritative-lane-derived-cache.md),
[0032](0032-lane-field-in-pipeline-state-and-index-writers.md),
[0033](0033-stakes-first-class-with-path-glob-detection.md),
[0034](0034-light-verify-one-iteration-cap.md),
[0042](0042-dynamic-mid-flight-lane-correctness.md),
[0074](0074-lane-conditional-planning-no-planner-spawn-on-fast-lanes.md)

## Context

The lane family grew one decision at a time, and each was locally reasonable.
ADR-0030 routed a ticket to one of four lanes from a `size` × `stakes` grid.
ADR-0031 made those axes authoritative and the lane a derived cache. ADR-0033
made `stakes` independently detectable from path globs. ADR-0034 gave each
lane a verify depth and an iteration cap. ADR-0042 then made the lane
*dynamic*: three triggers could raise it mid-run, and a fourth path could
lower it with a recorded human confirmation. ADR-0074 made the plan phase
itself lane-conditional.

Seven decisions later, the cost is visible in one number: **`derive_lane` and
its dependents are called from five different skills at four different points
in a ticket's life**, and no two of those calls are guaranteed to agree.
`/acs:create-ticket` mints the axes. `/acs:analyze-ticket` recommends raising
`stakes` from a path glob and applies it through an escalation event.
`/acs:create-impl-plan` recomputes the lane to decide whether to spawn a
planner and whether the plan needs approval. `/acs:code` recomputes it again
at Start (explicitly forbidden from trusting the cached value, NFR-S4), forks
its verifier on it, and may raise it again mid-loop. `/acs:ship` recomputes
the depth a third time to decide whether to stop at its context boundary.

Three consequences followed.

**The routing decision reads the wrong evidence.** `size` and `stakes` are
set when the ticket is written — before anyone has looked at the code. The
axes are a guess about the work; the plan is a description of it. By the time
`/acs:create-impl-plan` has produced a file map, a spec list, a test strategy
and a risk register, the ticket's original `size: small` is the least
informed thing in the partition, and it is still what routes the run.

**Mid-flight escalation is machinery paid for on every run to serve a rare
one.** The three triggers, `guard_axes`, `escalate_lane`, the 13-field
escalation event, the monotone ceiling raise, the resume-idempotency
argument, and the boundary-only confirmation sequence with its clarification
round-trip exist because the *initial* routing was known to be unreliable.
They are a correction loop for a classification made too early.

**One 750-line skill carries four protocols.** `/acs:code` describes the
TRIVIAL run and the COMPLEX run in the same body, forked at read time by
`verify_depth`. Every run loads all four, and the two cheap paths pay the
context cost of the two expensive ones — while the expensive paths' real
cost, the subagent fan-out, is buried in a conditional rather than declared.

## Decision

**The delivery path is classified once, from the plan, by `/acs:ship`, and
recorded.** After `create-impl-plan` completes, the ship coordinator reads
`plan.md` — its file map, spec count, API-surface finding, risk register and
documentation map — and judges the ticket onto exactly one of four paths:
`trivial`, `small`, `standard`, `complex`. The judgement and its reason are
written once to `pipeline-state.json` as `delivery_path` and
`delivery_path_reason`. **A resumed run reads the recorded path; it never
re-judges.** That is what makes the classification stable across sessions and
what lets the machinery below be static.

This is deliberately a judgement, not a scoring function. A plan's weight is
not a count — twelve files of mechanical renaming is a smaller change than
one file of new authentication logic — and a threshold over file counts would
have to be wrong in one of those two directions. The evidence the coordinator
reads is bounded and named, the verdict is one of four values, and the reason
is recorded next to it, which is the accountability a scoring function would
have offered without the brittleness.

**`workflows/ship.yaml` declares the paths, and every branch is data.**
Version 2 adds a top-level `delivery:` block naming the classification point
and the path vocabulary, and a per-step `paths:` filter. A step whose `paths:`
excludes the active path is recorded `skipped`, exactly as a false `when:`
predicate already records it — and because the walk already counts `skipped`
as satisfying a `needs` edge, the four paths reconverge on `create-pr` with no
new DAG semantics at all. A step's `skill:` may be a mapping keyed by path,
which is how one `code` step resolves to one of four implementations while
keeping a single ledger key.

**Four `code` legs replace the runtime fork.** `code-trivial`, `code-small`,
`code-standard` and `code-complex` are internal legs of `code` (the mechanism
ADR-0091 introduced and `phases.yaml` already carries), each with its own
SKILL.md, its own `agents` entry, and one protocol rather than four:

| | trivial | small | standard | complex |
|---|---|---|---|---|
| Executors | one | one | parallel, per file map | parallel, per file map |
| Verifier | single pass, core dimensions | single pass, all dimensions | single pass, all dimensions | four lenses + merge |
| Iteration ceiling | 2 | 2 | 3 | 3 |
| Plan approval | not required | not required | required | required |
| `create-test-docs` | skipped | runs | runs | runs |
| ship context boundary | no stop | no stop | stop | stop |

The ceiling is 2 rather than 1 even on the cheapest path, for the reason
ADR-0034 was amended on 2026-09-14: a cap of 1 leaves a run no round in which
to fix what its own verifier found, and the release-gate measurement lost one
run in two to a single fixable coverage finding.

**The size and stakes axes are retired.** `derive_lane`, `verify_depth`,
`VERIFY_ITERATION_CAP`, `lane_rank`, `LANE_ORDER`, `escalate_lane`,
`guard_axes` and `recommend_stakes` are deleted, along with
`record_escalation_event`, `confirm_deescalation`, the `acs.py lane apply`,
`lane deescalate` and `stakes recommend` commands, the `high_stakes_paths`
setting, and the `size`/`stakes`/`lane` fields on the ticket. The
verifier's approval-audit dimension, which existed to catch a stakes
escalation that was never recorded, becomes a **path audit**: a changeset
whose shape contradicts the path it was routed on is a finding.

## Consequences

**What gets better.** One classification, at the one point where the evidence
exists, recorded once. A cheap ticket loads a cheap protocol and spawns cheap
machinery; an expensive one declares its expense in `ship.yaml` where a
reviewer can see it. The correction loop disappears because the thing it was
correcting — a guess made before the work was understood — is gone.

**What gets worse, and why we accept it.** Rigor can no longer rise on
evidence discovered mid-implementation. If the executor finds the work is
larger than the plan described, the run finishes on the path it started on.
We accept this because the honest response to "the plan was wrong" is
`on_replan` — which `ship.yaml` already declares, which re-runs
`create-impl-plan`, and which then re-classifies from the corrected plan.
That is a better correction than raising a ceiling mid-loop, because it fixes
the artifact everything downstream reads rather than compensating for it.

**This is a breaking change.** A consumer's `.acs/workflows/ship.yaml` at
version 1 is refused with a message naming the migration; tickets carrying
`size`/`stakes`/`lane` keep them as inert data that nothing reads. It ships
in v0.5.0, alongside the skills-independence refactor, under the same
migration note.

**The context saving is modest; the machinery saving is not.** Four leaner
bodies save a few hundred lines on the cheap paths. The change that matters
is that a trivial ticket now runs one executor and one verifier over a core
dimension set, where it previously ran the same fan-out the complex path runs
and differed only in a ceiling.
