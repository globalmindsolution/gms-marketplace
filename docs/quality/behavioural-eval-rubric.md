# Behavioural eval rubric

What an artifact-level eval must assert to count as evidence, and what makes
one green.

The layers below this one are cheap and already complete: structure is 28 of
32, gating 17 of 17 hooked, routing 32 of 32 (enforced mechanically by
`tests/evals/check_cases.py`, run locally). They prove that a skill *ships*,
that it *refuses* what it must, and that a request *reaches* it. None of them
proves it **produced the right thing** — and that is the only layer a user
would notice missing.

Behavioural coverage is **2 of 32** (`create-ticket`, `code`), as artifact
cases under `plugins/acs/evals/artifacts/` — and neither has yet completed end
to end (see that folder's README). `create-pr` had a third, a forge-tier
scenario against a live GitHub remote; it went with the retired behavioural
harness, and the eval sandbox cannot reach GitHub. PRD **G31** commits to
closing the gap. This rubric says what closing it means, so that the thirty
cases still to be written are worth the money they cost.

> A behavioural eval asserts on the **artifacts a skill produced**, never on
> what it said while producing them.

That rule is not new — `plugins/acs/evals/artifacts/README.md` and
[`README.md`](README.md) both state it. What follows is what it takes to
satisfy it.

## What a scenario must assert

A scenario counts as behavioural evidence for a skill when all four hold.

### 1. It reads the workspace, not the transcript

The assertion target is a file the skill wrote: `ticket.json`,
`run.json`, a `steps/<skill>/state.json` invocation, a result document, a
doc under the consumer's `docs/` tree, a branch, a commit, a PR. If the
scenario would still pass with the model's prose replaced by lorem ipsum, it is
asserting the right thing.

An assertion on stdout is allowed only where stdout **is** the contract — a
gate's refusal text, `acs.py`'s JSON on stdout — and then it is a deterministic
check that belongs in the free tier, not a paid session.

### 2. It asserts shape *and* value

`ticket.json exists` is not evidence. `s02` is the standard to copy: the ticket
appears in the index under its own id, the gate names the input it is missing,
and the gate opens once that input exists. Each of those fails if the skill
does the job badly, not merely if it crashes.

The question to ask of every assertion: **what plausible defect does this
catch?** An assertion with no answer is decoration, and it makes the suite look
stronger than it is — the failure mode the whole eval programme exists to
avoid.

### 3. It spends only when it must

Every `claude plugin eval` case spawns a real session, so every case costs
money. What a case may choose is how it is *graded*: `regex`, `tool_used`,
`tool_order` and `file_exists` graders are free and deterministic, while `llm`
and `baseline` graders add a judge call per vote. Prefer the free graders; keep
`llm` for short outputs, with rubrics written as concrete PASS and FAIL
conditions.

Anything that needs no model at all is not an eval case. It belongs in
`tests/` — which is where the old harness's free-tier checks went when it was
retired, and why the no-ticket refusal on `/acs:code` is now a unit test
rather than a scenario.

A case that asserts something a unit test could have asserted is a defect: it
buys with money what determinism gives away.

### 4. Its preconditions are real

The case's scaffold must actually satisfy what its prompt presupposes. This is the failure that already bit us: two routing probes split
4-of-5 not because a description was weak but because the seeded repo made the
prompt false — the model looked for the thing, did not find it, and asked
instead of acting. It was **first mis-triaged as a description defect**.

So: if a prompt says "the code change is done", the scaffold must commit a
change. If it says "this repo has no tooling", the workspace must be bare. A
case whose presupposition is false measures the scaffold, not the skill.

**Three routing cases break this rule today**, knowingly:
`route-create-design`, `route-create-requirements` and `route-docs-sync` each
presuppose context (an epic ticket, an existing codebase, a finished change)
and run in an empty workspace. Each case's `description` records it as a known
confound. Seeding them is the fix; until then a miss on one of them is not
evidence against its description.

## Grading a scenario's outcome

| State | Meaning |
|---|---|
| **pass** | every assertion held |
| **fail** | an assertion did not hold — a defect in the skill, or a wrong expectation, triaged like any other |
| **skipped** | the tier could not run (no `claude`, no forge target) — clean exit, and **never counted as coverage** |
| **unmeasured** | the scenario exists but has never been executed against this build |

`skipped` and `unmeasured` are the two states that quietly inflate a coverage
number, so neither may be reported as a pass. `acs-evals` already holds this
line for its own tier — `make perf` reports **UNMEASURED and fails** until a
measurement exists, "absence is not a pass" — and the routing harness counts an
undecidable probe as "a miss, never a pass". Same default here.

## Severity, when one fails

The same three levels the retired eval rubric defined, asking its same
question — *if this failed on a released build, what can go wrong for a
consumer?* — applied to artifacts rather than CLI output:

- **critical** — the artifact a later step depends on is wrong or absent, so
  the pipeline proceeds on bad evidence: a ticket recorded against the wrong
  id, a run entry that says `completed` for work that did not finish, a PR
  opened with no recorded verifier pass.
- **major** — the artifact is present and correct enough to proceed, but a
  documented key moved: a missing `states` key, a changed result-document
  shape, a doc written to the wrong configured path.
- **minor** — cosmetic content inside an artifact nothing reads.

Ties go to the higher level, for the reason the sibling rubric gives:
over-classifying costs a conversation, under-classifying is how a real defect
ships green.

## Which twenty-eight to write first

Not alphabetically, and not cheapest-first. Order by what a wrong artifact
would cost:

1. **Skills whose output another skill consumes.** `create-impl-plan` (the
   plan `/acs:code` executes), `analyze-requirements`, `create-api-contract`,
   `create-test-docs`. A wrong artifact here is not noticed until a later step
   has already acted on it — the `critical` failure mode above, exactly.
2. **Skills that write to the consumer's repo.** The doc-bootstrap legs,
   `project`, `docs-sync`. Their output is what the user actually keeps.
3. **Skills that mutate shared state.** `merge-pr`, `release`.
4. **Session bookkeeping.** `handoff` — named in PRD G8 as today's
   trigger-only gap, and genuinely the lowest risk of the four.

Where the skill needs a real codebase, have the case's `scaffold_script`
build one rather than prompting against an empty workspace, so that
precondition 4 holds by construction. (A fixture app used to exist for this;
it was retired with the root `evals/` folder.)

## What this rubric does not do

It does not say whether the artifact's **content** is any good — whether a
generated plan is a sensible plan, or a doc set is well written. That is a
judgement about the skill, and it belongs to
[`skill-rubric.md`](skill-rubric.md), which grades the skill rather than the
evidence.

It also does not set a coverage target. **G31** owns that (100% of user-facing
skills, monotonically non-decreasing, within two releases of the delivering
capability). This document only defines what may be counted toward it.
