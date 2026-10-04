# 0092 — Skill machinery is declared per skill, not assumed: four work classes, and the planner/executor/verifier trio stops being the default

**Status**: Accepted · **Date**: 2026-09-13

**Supersedes**: [0077](0077-docs-sync-remediation-loop-execute-verify-only.md),
[0078](0078-create-project-remediation-loop-execute-verify-only.md),
[0079](0079-standardize-project-remediation-loop-execute-verify-only.md),
[0083](0083-bootstrap-doc-skills-remediation-loop-execute-verify-only.md),
[0084](0084-create-architecture-design-requirements-remediation-loop-execute-verify-only.md)
— the five per-skill "execute + verify, no planner" decisions, each of which
this ADR generalises into class D. Stated in the index since this ADR landed;
recorded here so the link is machine-readable in both directions.

## Context

acs ships 32 skills, 59 subagent files, 9,812 lines of agent prose and 12,261
lines of skill prose — roughly 22,000 lines of instruction. Nineteen skills
carry a full `planner` / `executor` / `verifier` trio.

No decision ever put that trio on those nineteen skills. It is produced by one
line in `tests/acs/test_skill_contracts.py`:

```python
roles = {skill: list(ROLES) for skill in HOOKED_SKILLS}
roles["code"] = ["executor", "verifier"]
```

— with the comment *"Every skill is a triad except /acs:code"*. The shape is
asserted, and a skill that wanted a different one had to be carved out by hand.
Only `code` ever was. ADR-0083 came at the same problem from one side (it
dropped the per-iteration planner re-spawn across the bootstrap-doc family) but
left the trio itself in place everywhere.

Three consequences are already visible on disk.

**Three skills forbid what they ship.** `create-pr`, `create-ticket` and
`merge-pr` each state in their own prose that they perform their work inline
and must *never* spawn a planner or a verifier. All three ship
`<skill>-planner.md` and `<skill>-verifier.md` anyway. Nothing spawns them; the
only things referencing them are the contract tests asserting they exist and
`INTERNALS.md` listing them. The tests are holding the redundancy in place. The
structural tell is sharper still: none of these three has a reflection loop at
all — no plan→execute→verify round exists to put a planner in — yet each also
carries lane and verify-depth prose written for a loop it does not run.

**A planner plans the planning skill.** `/acs:create-impl-plan` exists to
produce one artifact, `plan.md`. It spawns `create-impl-plan-planner`, whose
charter is "turn a ticket into a concrete, executable TDD plan" — the
deliverable itself — and then an executor and a verifier besides. Four agents
and an XML task contract to write one document. `/acs:analyze-ticket` has the
same shape: a planner to plan an analysis.

**The heaviest skill is the least reliable one.** The 2026-09-13 tier-3
measurement put `PIPE-code` — `code` is 889 lines with an executor, a verifier
and up to three verify iterations — at 1 of 3 runs completed, two hitting the
1800-second wall. `PIPE-create-ticket`, which does its work inline with at most
one executor, completed 3 of 3 at $0.52 median. Three runs a side is
suggestive, not conclusive, and the causal claim is explicitly not made here;
what it does establish is that machinery is not free and that the suite can
measure the difference.

## Decision

**A skill declares the machinery it needs. The contract test enforces the
declaration, not a default.** `AGENT_ROLES` stops being derived from
`HOOKED_SKILLS` and becomes a registry entry per skill, so choosing a shape is
a reviewable decision and a skill with no loop cannot silently keep a planner.

Skills are designed against four classes, by the kind of work they do:

| Class | Work | Machinery |
|---|---|---|
| **A · Mechanical** | A deterministic action with no judgement: write hook files, read state, print a dashboard. | No subagents, no loop, no lanes. |
| **B · Dispatch** | Choose and invoke other skills; do none of the work. | No subagents, no loop. |
| **C · Apply-with-a-gate** | The judgement is a *readiness check*; the action that follows is mechanical. | Inline, with at most one executor. No planner, no verifier — the gate runs before the action rather than reviewing it after. |
| **D · Authoring** | Produce a document someone will rely on. | Executor + verifier. **No planner** — when the deliverable *is* the plan or the analysis, a planning phase to plan it is a second copy of the work. |
| **E · Implementation** | Write production code and tests against a plan. | Executor + verifier, with iteration. Unchanged. |

The rule that generates class D's shape is the general one: **a planner earns
its place only when planning and doing are genuinely separate work.** For
`/acs:code` they are, which is why the plan moved out to
`/acs:create-impl-plan`. For a skill whose output is a document, they are the
same act.

A verifier earns its place when an *independent* reading of the artifact
against its inputs can catch something the author cannot see. That is true of a
document (class D) and of a changeset (class E). It is not true of class C,
where the check is a gate that runs before the action, not a review after it.

### Per-skill assignment

| Class | Skills | Agents now → then |
|---|---|---|
| A | `setup`, `install-hooks`, `update`, `metrics`, `usage`, `handoff`, `test` | 0 → 0 (correct already) |
| B | `ship`, `create-docs`, `project`, `release`, `run-e2e-tests` | 0 → 0 (correct already) |
| C | `create-pr`, `create-ticket`, `merge-pr` | 9 → 3 |
| D | `analyze-ticket`, `create-api-contract`, `create-architecture`, `create-design`, `create-e2e-tests`, `create-impl-plan`, `create-operations`, `create-prd`, `create-principles`, `create-project`, `create-quality`, `create-requirements`, `create-standards`, `create-test-docs`, `docs-sync`, `standardize-project` | 48 → 32 |
| E | `code` | 2 → 2 |

**59 agent files → 37.** Twenty-two removed: six that their own skills already
forbid, sixteen planners for skills whose deliverable is the plan.

The three class-C **executors stay.** Each of those skills says it delegates to
"at most one executor", and that delegation is real work kept out of the
coordinator's context. Only their planner and verifier are unreachable. An
earlier draft of this ADR put class C at nine files removed and called the lot
pure subtraction; that was wrong about the executors, and removing them would
be a behaviour change owing a measurement rather than a deletion owing none.

Classes A and B need no change at all — eleven skills were already the right
shape. The redesign is not a rewrite of everything; it is the removal of
machinery from the twenty that acquired it by default.

### What is NOT removed

**`/acs:test` stays.** It is the obvious candidate — a 24-line deprecated alias
whose own prose says it is "retained for ONE release" — and removing it now
would be a mistake. Released 0.4.9 ships `test` and has never shipped
`run-e2e-tests`: the rename is still unreleased. Every existing user has
`/acs:test` in their fingers and will meet the rename for the first time when
0.5.0 lands. The alias is the migration path for the release *ahead*, not a
leftover from one behind, and it is removed one release after 0.5.0, not
before it.

**The four doc legs keep their own agents for now.** `create-quality`,
`create-operations`, `create-principles` and `create-standards` are
structurally near-identical (359–401 lines each) and will hold eight agent
files between them for work that differs only in which directory it writes.
Collapsing them onto one shared pair is a real further saving and a separate
decision, because it trades per-leg specificity for uniformity — the same trade
this ADR is undoing elsewhere, and it deserves its own evidence rather than
momentum.

## What this supersedes

Five ADRs said one thing five times. **0077** (docs-sync), **0078**
(create-project), **0079** (standardize-project), **0083** (the five
bootstrap-doc skills) and **0084** (create-architecture, create-design,
create-requirements) each decided that their family's remediation loop is
*execute — verify only*: the plan is authored exactly once per run, before
the loop starts, and later findings route to the executor rather than to a new
plan. Eleven skills, one decision, restated per family because there was no
place to state it once.

This ADR states it once, for the authoring class, and follows it to its
conclusion. A plan authored once and never revisited, for a skill whose
deliverable *is* a document, is a first draft — and a first draft does not need
its own agent, its own XML task contract and its own charter. Those five are
superseded here.

It also inherits a relocation. **0037**, **0038** and **0039** scoped a
spec-time simplicity gate to `create-spec-planner`; ADR-0066 folded spec
authoring into `/acs:code`, ADR-0089 moved that plan phase out to
`/acs:create-impl-plan`, and the gate travelled with it. Removing
`create-impl-plan`'s planner moves it once more — into the skill and its
executor, which is where it lands rather than where it dies.

## Consequences

- Per-role `models` configuration for a role a skill no longer has becomes
  inert. Settings keep accepting it; nothing reads it.
- `INTERNALS.md`, `AUTHORING.md` and the skills table stop describing a
  universal trio.
- The contract tests change from asserting a shape to asserting a declaration,
  which is what stops this recurring.
- **Each class lands as its own change, measured.** "Simpler is more reliable"
  is a claim, and this repo owns the instrument that tests it: tier 3 reports
  reliability, cost and time per skill, and since 2026-09-13 records the skill
  sequence of every pipeline run. The six class-C planner/verifier files are
  unreachable, so deleting them is pure subtraction and needs no measurement.
  Every other change here alters behaviour and is measured before and after, or
  the simplification is just a different guess.

## Amendment — stage 2 landed (2026-09-14)

Class D is applied in full. `/acs:create-docs` went first (ADR-0094); the
other twelve authoring skills — `analyze-ticket`, `create-impl-plan`,
`create-api-contract`, `create-test-docs`, `create-e2e-tests`, `create-prd`,
`create-design`, `create-architecture`, `create-requirements`,
`create-project`, `standardize-project`, `docs-sync` — followed in one
change, each editing its own `agents:` line in `workflows/phases.yaml`.
`plugins/acs/agents/` holds **31** files: 14 executor + verifier pairs and
the 3 apply-work executors. The count differs from the 37 the table above
projected because ADR-0094 collapsed the four doc-set legs into one pair
(−6) in between.

What "no planner" turned out to mean in practice, since the shape is the
same in all twelve:

- The planner's charter did not disappear; it moved into a
  `## Survey — what you establish before you write (iteration 1)` section of
  the executor. Iteration 1's executor surveys first, records the survey in
  `iter-<n>-authoring.md` (the notes ADR-0094 introduced), and authors the
  deliverable from it. An open decision comes back as `needs_input` **before
  any file is written** — the same stop the planner used to provide, one
  spawn earlier.
- The verifier gains an `authoring-conformance` dimension: the deliverable
  is what the notes surveyed, every citation in the notes re-opens, and a
  draft with no notes behind it is a blocking finding on its own. The
  deterministic floors that used to parse `iter-1-plan.md`
  (`prd_conformance_check.py`, `citation_check.py`,
  `/acs:standardize-project`'s frozen allowlist, `/acs:create-project`'s
  pinned scaffold) parse the notes instead — the file they read moved, the
  check did not.
- `/acs:create-impl-plan` keeps ADR-0074's lane rule with its executor in
  the planner's place: on STANDARD/COMPLEX the executor's survey (the former
  `code-planner` charter, spec-simplicity gate and oversize signal included)
  renders the `plan.md` draft; on TRIVIAL/SMALL the coordinator authors it
  and no executor is spawned.
- `/acs:create-e2e-tests` declares its file map as the e2e root directory
  rather than a planner's file list — `path_in_filemap` matches directory
  entries as prefixes for it.
- `models.planner` and `models.overrides.<skill>.planner` stay accepted and
  are inert, as the Consequences above said they would be.

The measurement this ADR's last consequence asks for is the release gate's:
the stage-2 tree is measured against the last passing baseline before it
ships, on the same scenarios, and the comparison is recorded with the
release.

## Amendment — v0.5.0 (the implementation-pipeline redesign)

The four work classes and the per-skill declaration stand, classes B–E landed,
and nothing here is reconsidered. One explicit non-removal was reversed.

**"`/acs:test` stays" did not survive the release it was reasoning about.** The
argument was sound and time-bound: released 0.4.9 ships `test`, has never
shipped `run-e2e-tests`, and users would meet the rename for the first time on
upgrade. v0.5.0 is that upgrade. The alias directory is deleted, `run-e2e-tests`
is the skill, and it moved into `HOOKED_SKILLS` as a step of `ship.yaml` with
its own pre/post pair — so the "not really a pipeline skill in its default
mode" framing went with it and there is one mode, not two.

Two vocabulary notes for reading the class table. "No subagents, no loop, no
lanes" (class A) is now no delivery paths — lanes were retired by
[0095](0095-static-delivery-path-routing.md) and the four `code-*` legs are
dispatched from the plan's recorded path
([0098](0098-delivery-path-recorded-on-the-plan.md)). Class D's "a planning
phase to plan it is a second copy of the work" is unchanged and is exactly why
`/acs:create-impl-plan` has an executor and a verifier and no planner of its
own.

The agent-file count moved again with the redesign: `/acs:code` keeps only
`code-executor`, its verifier having left for `/acs:review-code`
([0099](0099-review-is-a-step-not-a-phase.md)), which brought two agents of its
own (`review-code-lens`, `review-code-adjudicator`).
