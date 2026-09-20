# Redesign: the implementation pipeline (v0.5.0)

**Status**: Proposed · **Date**: 2026-09-19 · **Scope**: implementation skills only

This document specifies a from-scratch redesign of acs's **implementation**
half — the skills `/acs:ship` orchestrates between a settled requirement and an
open PR. The **design** skills (`create-prd`, `create-requirements`,
`create-architecture`, `create-docs`, `project`, `create-ticket`,
`create-design`) are out of scope and keep their current shape.

It is a **breaking redesign with no backward-compatibility layer**. State
written by v0.4.9 is not read by v0.5.0; there is no dual-read release and no
migration of in-flight runs. Finish or abandon open runs before upgrading.

## 0. This ships AS v0.5.0, not after it

v0.5.0 is **not yet released**. The installed plugin is v0.4.9, and the entire
surface this redesign removes exists only on unreleased `main`:

| Removed or renamed by this redesign | In released v0.4.9? |
|---|---|
| `analyze-ticket` (renamed here) | **no** |
| the verifier inside `/acs:code`, and the legs' per-path verifier shape | **no** |
| `ship.yaml`, `phases.yaml` — the whole `workflows/` layer | **no** — the directory does not exist in 0.4.9 |
| ticket-keyed state partitions | yes |
| `test` alias | yes (already deprecated) |

Cutting v0.5.0 from current `main` and *then* applying this redesign would
publish a workflow layer and eleven new skills to consumers, then re-cut every
one of those skills' contracts and rename one of them weeks later. Consumers
would migrate twice, the second time out of a surface that had existed for
days. Nothing on unreleased `main` is a fix consumers are blocked on — v0.4.9
already resolved the in-repo state-root blocker that made v0.4.8 unusable.

So there is no v0.6.0 in this plan and no interim cut: **v0.5.0 is the
redesign**, measured and released once, against the tree that results from
P1–P6.

---

## 1. Why

The current implementation pipeline works, but four properties of it block
where the product is going.

**1. The state machine cannot hold more than one workflow.** Every state file
is keyed by *skill name*: `pipeline-state.json`'s `steps` object, the
`<skill>-state.json` files, and the `phases/<skill>/` artifact directories.
`pipeline-state.schema.json` closes `steps.propertyNames` to a hard-coded
**18-name enum**, and `flow` to a 2-value enum (`ticket`, `product`). No file
records a workflow name, version, or instance. Consequences: a new workflow is
a schema edit; two workflows cannot share a skill; the same workflow cannot
run twice on one subject. §4.1 lists what is on disk and the six things wrong
with it.

**2. The review is inside the thing it reviews.** `/acs:code` spawns its own
verifier, so the implementation skill grades its own output, and the review's
rigor is configured by picking one of four `/acs:code` legs. That coupling
produced two measurable problems: the full unit suite runs inside an execute
→ verify iteration that may be discarded, and per-finding adjudication exists
on exactly one delivery path (`complex`) while `trivial`, `small` and
`standard` block on unscrutinised single-verifier findings.

**3. A ticket id is mandatory.** The partition is
`<workspace>/<repo-id>/<ticket-id>/`, so nothing can run without one. That
makes the pipeline unusable for the most common case — a developer with a
prompt and a repo.

**4. The workflow carries predicates the skills should own.** `ship.yaml`
version 2 decides for a skill whether it has work: `when: api_surface_changed`,
`paths: [small, standard, complex]`, `requires: design_approved`. A skill whose
applicability is decided by a workflow predicate cannot be run on its own and be
trusted — invoked by hand it never evaluates the condition that the workflow was
evaluating for it. The predicates also make `skipped` the audit record for two
different things: *the plan said this was not owed*, and *nobody asked*.

---

## 2. The pipeline

Ten steps, declared in `workflows/ship.yaml`. `/acs:ship` is a **pure
orchestrator**: it reads the workflow, invokes each step in order, and records
state. It contains no step logic of its own.

**`ship.yaml` carries no conditions and no constraints.** No `when:`, no
`paths:`, no `requires:`, no `needs:` — the declared order *is* the dependency
order, and every step runs on every run. This is the load-bearing simplification
of the redesign, and it follows from the standalone-skill rule: a skill that can
only be understood alongside a workflow predicate is not standalone. Each skill
decides for itself whether it has work, and records a positive, evidenced no-op
when it does not.

So `create-api-contract` on a change with no API surface does not get skipped by
the workflow. Its **pre-hook** reads the plan's `## Contract` block, finds
`api_contract: false`, records the step completed with
`outcome: no_surface_owed` and the plan's reason — and the skill's coordinator
is never spawned. Milliseconds, zero tokens. The same holds for
`create-test-docs`, `create-e2e-tests` and `run-e2e-tests`. The audit trail
gains a step that says *why* nothing was owed, which a `skipped` status never
carried, at the price v2 paid for `skipped`: nothing.

```
 1  analyze-requirements   clarify the requirement from a ticket, a prompt or a document
 2  create-impl-plan       plan mode: read-only until the human approves the plan
 3  create-api-contract    the API/data contract, or an evidenced "none owed"
 4  create-test-docs       test-cases.md — the TC-n set code and review both trace to
 5  code                   implement with TDD — targeted tests only; dispatches to its leg
 6  review-code            five-lens review + adjudication + final gate    ← loops with 5, cap 3
 7  create-e2e-tests       the e2e tests the plan declared, or an evidenced "none owed"
 8  run-e2e-tests          run them
 9  docs-sync              re-derive and apply the doc deltas
10  create-pr              create the branch, push, open the PR
```

Steps 5 and 6 form a loop with a **cap of 3 iterations**. The run stops at
`create-pr`; merging stays a human action through `/acs:merge-pr`.

**There is no `needs:` either.** In version 2 `needs:` bought three things: the
dependency order, the property that a skipped step still satisfies a downstream
edge, and parallelism. The first is redundant the moment the steps are written
in order. The second is void once nothing is skipped. The third had exactly one
use — `docs-sync` beside the e2e pair — and a dependency graph, a scheduler and
a `max_parallel` knob are a poor price for one step's wall-clock. Ten steps run
in the order they are written.

What remains is a **list**, which is the whole point: the pipeline's shape is
legible by reading it top to bottom, and `acs run next` is "the first step
not yet completed" rather than a graph traversal.

### 2.1 `workflows/ship.yaml` (version 3)

```yaml
version: 3

steps:
  - analyze-requirements
  - create-impl-plan
  - create-api-contract
  - create-test-docs
  - code
  - review-code
  - create-e2e-tests
  - run-e2e-tests
  - docs-sync
  - create-pr

loops:
  - from: review-code
    back_to: code             # on blocking findings, re-enter at `code`
    max_iterations: 3         # counts code→review-code rounds
    on_exhausted: fail        # never "pass with findings"
```

That is the entire file: a version, a list of skill names, and the one loop.

**No `id:`.** A step is a skill; with no conditions and no reuse of a skill
inside one workflow, an `id` would name nothing the skill name does not.
State is keyed by skill name (§4.2). **No `name:`** — the file name is the
name, and `run.json` records it as such. **No `stop_after:`** — the list ends
where the run ends; `merge-pr` is not in it.

**`loops:` is the only construct, and it is not a condition.** A loop tests
nothing about the change — it declares that two steps form a cycle and how
many times. That cannot live inside a skill, because it spans two of them:
today the execute↔verify loop lives *inside* `/acs:code`, which is precisely
why the review cannot be a separate skill. Moving the loop into the workflow
is what lets `/acs:review-code` be standalone, and it is the crux of this
redesign. It is a top-level list rather than a key on a step for the same
reason: it belongs to the pair, not to either member.

**Where the removed predicates went.** Nothing is lost; each moves to the party
that can evaluate it from its own inputs:

| Version 2 | Version 3 |
|---|---|
| `when: api_surface_changed` | `/acs:create-api-contract` reads the plan and records an evidenced no-op |
| `when: plan.test_cases_required` | `/acs:create-test-docs`, the same way |
| `when: e2e_configured`, `when: post_code_test_active` | `/acs:create-e2e-tests` and `/acs:run-e2e-tests`, the same way |
| `requires: design_approved` | `/acs:create-impl-plan`'s own start check, where the approval file already lives |
| `delivery:` + per-path `skill:` mapping | the plan records the path; `/acs:code` dispatches to its leg (§3.5) |
| `needs:`, `max_parallel`, `exclusive` | the written order |
| `on_fail: relay_to` | the `loops:` entry above, for the one loop there is |
| `id:`, `name:`, `stop_after:` | the skill name, the file name, the end of the list |

### 2.2 What a simple ticket costs

The workflow's shape is fixed; its cost is not. A trivial ticket must stay
cheap, and the legs alone do not make it so — they shrink the implementation
side, which was never where a trivial ticket's cost was. Three mechanisms
carry the saving, none of them a workflow condition:

1. **No-ops are decided by the pre-hook**, from `## Contract`, before any
   coordinator exists. Four of the ten steps cost nothing on a ticket that
   owes nothing.
2. **The review scales by its inputs, not by a rigor setting** (§3.6). Lens C
   has nothing to check without a contract or a design and does not run;
   lens B fans out by diff size; adjudicators are one per finding, and a
   trivial diff has few. What does not scale down is what makes the review a
   review: lenses A, B, D and E, per-finding adjudication, and the gate.
3. **The leg** picks one executor and skips plan approval.

In counts, on a trivial ticket with no API surface and no e2e impact:

| | v2 `trivial` | **v3 `trivial`** | v3 `standard` |
|---|---|---|---|
| Coordinator turns | 5 | **6** + 4 hook-only | 10 |
| Executors | 1 | **1** | per file map |
| Reviewer agents | 1 verifier | **4 lenses** + one adjudicator per finding | 5 lenses (B fanned out) + adjudicators |
| Full unit-suite runs | 1 per verify iteration (≤2) | **1 per surviving iteration** (≤3) | same |
| Plan approval | no | **no** | enforced |
| e2e | skipped | **hook no-op** | authored and run |

Read honestly: v3 trivial is **one coordinator turn and three agent spawns
more** than v2 trivial, and the same everywhere else. What the difference
buys is what §1.2 asked for — per-finding adjudication and a git-history lens
on the cheapest path, which v2 trivial had neither of, and a review that is
not inside the thing it reviews. Against v3 `standard` it is less than half
the agent work, which is the ratio PRD G14 measures.

---

## 3. The skills

Every skill below is **independently invocable**. `/acs:ship` gives a skill
nothing it could not resolve itself from state and arguments; running
`/acs:review-code` by hand on a dirty working tree is a supported first-class
use, not a debugging affordance.

### 3.1 `/acs:analyze-requirements` *(renamed from `analyze-ticket`)*

Accepts **any one of**: a ticket id, a free-text prompt, or a path to a
document. None is required by the pipeline; supplying none is an error only at
this step, not at the gate.

Produces `requirements.md`: the requirement restated, its acceptance criteria
made concrete and testable, the open questions resolved through the
clarification ledger, and an explicit out-of-scope list. Where a ticket id was
supplied, the ticket remains the authority and is re-read fresh; where a prompt
or document was supplied, this artifact *becomes* the authority for everything
downstream.

### 3.2 `/acs:create-impl-plan`

Its input is now `requirements.md` rather than a ticket, and **it works the way
Claude Code's own plan mode works**. That is a deliberate borrowing of a shape
that is already proven, already familiar to every user of this tool, and already
solves the problem acs's plan step solves badly today.

Four properties, taken from plan mode and binding here:

1. **Read-only until approved.** The skill investigates the repo with read and
   search tools only. No `Write`, no `Edit`, no mutating `Bash`. Enforced by a
   `PreToolUse` hook for the duration of the step, not by instruction — the same
   mechanism that gives plan mode its guarantee.
2. **The plan is written for a human to approve in one read.** Concrete steps
   against real paths, the approach and the alternative rejected, and what is
   explicitly not being done. Not a templated document with a section per
   heading whether or not that heading has content; prose and bullets, as short
   as the change allows.
3. **Approval is an explicit act and it is the gate.** The plan is presented and
   the human approves it, sends it back with feedback, or rejects it. Feedback
   re-enters planning rather than leaking into implementation. Nothing
   downstream may write code before that approval exists.
4. **Approval binds to the text that was approved.** `plan-approval.json`
   records `plan_sha256` over the approved plan, and an edited plan is an
   unapproved plan. This part acs already has and plan mode does not; it is what
   makes the approval survive a resumption hours later.

**Modelled on plan mode, not built with it.** `INTERNALS.md` records why the
reflection loop does not use `EnterPlanMode` / `ExitPlanMode`: those are for a
user at the keyboard, and subagents have none. That reasoning stands and
nothing here contradicts it. The four properties above are implemented by
acs's own hook and by `plan-approval.py`, and the party that stops for
approval is the coordinator, which does have a user. Under `/acs:ship` the run
pauses at this step on the paths that enforce approval (§3.5) — as it does
today.

Two things the plan carries that a plan-mode plan does not, because downstream
machinery reads them:

- **the file map** — the executor partition, and the contract the file-map guard
  enforces on every `Write`
- **the delivery path** — `trivial | small | standard | complex`, judged once,
  here, from the plan's own scope (§3.5). This is the only place it is judged,
  and it is recorded on the plan rather than in `ship.yaml`.

It does **not** author the API contract or the test cases. It states in plain
words whether they are owed, and steps 3 and 4 read that statement. It is no
longer a predicate the workflow evaluates — see §3.3.

**The machine-readable minimum.** "Not a template" does not mean "no
structure": three things downstream code reads must be findable without
parsing prose. `plan.md` therefore ends with one fixed section, and everything
above it is free-form:

```markdown
## Contract                       ← the only section with a fixed shape
delivery_path: standard           # trivial | small | standard | complex
owes:
  api_contract: true              # read by create-api-contract
  test_cases:   true              # read by create-test-docs
  e2e:          false             # read by create-e2e-tests / run-e2e-tests
  reason: "CLI-only change; no HTTP surface, no browser flow"

### Executor tasks & file map     ← unchanged heading; the file-map guard reads it
- task 1: src/acs/hooks/scripts/acs_lib/workflow.py, tests/acs/test_workflow.py
- task 2: src/acs/skills/ship/SKILL.md
```

The heading `## Executor tasks & file map` is kept verbatim because the guard
and `plan-approval.py` already key on it. `plan_sha256` hashes the whole file,
prose and contract alike, so editing either invalidates the approval. A skill
that needs a value reads the `## Contract` block and nothing else; a human
reads everything above it and need not read the block at all.

### 3.3 `/acs:create-api-contract`

Kept as its own step rather than folded into the plan. **It runs on every run.**
It reads the plan, decides for itself whether the change has an API or data
surface, and when it does not it records a completed step whose artifact says
so — the surfaces it checked, and why none is owed. That record is worth more
than the `skipped` it replaces: `skipped` never distinguished *the plan says
nothing is owed* from *the workflow never asked*.

The no-op is free. The decision is made by the skill's **pre-hook**, from the
plan's `## Contract` block, and recorded by `acs step finish --no-op` before
any coordinator is spawned: the invocation is refused with the message
"nothing owed — recorded", exactly as a gate refuses today. Invoked by
`/acs:ship` or by a developer, the answer is the same and the cost is the same.
The rule that decides it lives in the skill's own directory, not in the
workflow, which is what keeps the skill standalone.

When there is a surface it produces `api-contract.md`: endpoints, commands or messages with their
request/response shapes and error codes. Two downstream consumers depend on it
being a separate artifact rather than a section of the plan:

- `/acs:create-test-docs` reads its shapes when authoring test cases
- `/acs:review-code`'s **lens C** checks contract conformance against it — every
  item the contract specifies is implemented, and the changeset adds no public
  surface the contract does not describe

### 3.4 `/acs:create-test-docs`

Kept as its own step, and it too **runs on every run**, recording an evidenced
no-op when the plan's test strategy owes no cases. It is placed after
`create-api-contract` rather than beside it because test cases read the
contract's shapes when one exists.

It produces `test-cases.md`: the `TC-n` set. This is the artifact that makes
the split between `/acs:code` and `/acs:review-code` tractable —

- `/acs:code` takes its **targeted test set** from it, and names the `TC-n` id
  in each test's docstring
- `/acs:review-code`'s **lens A** rebuilds the acceptance matrix against it: a
  `TC-n` with no test, or a cited id that does not exist, is a finding

Without a shared `TC-n` vocabulary, "targeted tests only" has no definition the
reviewer can check, and the reviewer would be left inferring which tests the
implementer meant to write.

### 3.5 `/acs:code` and its four legs

Implements the plan with TDD. **Targeted tests only** — the tests its change
touches, never the full suite. It has **no verifier**: the review is step 6.

`ship.yaml` names `code`, one step and one ledger key. **`/acs:code` dispatches
to one of four legs** — `code-trivial`, `code-small`, `code-standard`,
`code-complex` — reading the delivery path the plan recorded (§3.2). The
dispatch is internal to the skill, which is why the per-path `skill:` mapping
disappears from the workflow without the legs disappearing with it. Invoked by
hand, `/acs:code` resolves the path the same way, from the same plan.

What the legs differ by, once the verifier has left:

| | trivial | small | standard | complex |
|---|---|---|---|---|
| Executors | one, always | one, rarely two | one per disjoint file-map partition | one per partition **+ an integration executor** |
| Test contract | the plan's test strategy | `test-cases.md` | `test-cases.md` | `test-cases.md` |
| Plan approval | not required | not required | **enforced** | **enforced** |

**The executor fan-out is what separates `standard` from `complex`.** Both
partition the plan's file map and spawn one executor per disjoint partition. On
`complex`, a final **integration executor** runs after the partition executors
finish and owns what no partition owns: the seams between them — the call sites
that cross a partition boundary, the shared type that two partitions changed
from different ends, the migration that has to land in one commit with the code
that reads it. It gets the union of the partitions' diffs as context and a file
map that is the intersection of their boundaries.

This is the concern `code-complex`'s four-lens verifier was implicitly covering:
a changeset too large for any one agent to hold is also a changeset whose seams
no single executor saw. Moving the review out leaves that gap on the
implementation side, and an integration pass is the direct answer to it —
cheaper than a second review and applied before the review rather than after.

> **A note on the word "lane."** This fan-out is deliberately *not* called a
> lane. In this repo `lane` names the retired `size` × `stakes` grid that
> ADR-0095 replaced with delivery paths, and five documents still say so.
> Reusing the term for executor parallelism would make every one of them read as
> a contradiction. They are executors, spawned per partition.

Two of the four axes the legs used to differ by are gone, and both leave for the
same reason — they were review properties, not implementation properties:

- **verifier shape** (one pass vs. four lenses merged and re-scrutinised) is now
  `/acs:review-code`'s business on every run
- **the iteration ceiling** (2 vs. 3 execute→verify rounds) is now the
  workflow's `loop.max_iterations`

Reviewer scale is **not** a leg input. `/acs:review-code` measures the changeset
in front of it and fans lens B out across the diff when the diff warrants it
(§3.6). That is how the four-lens depth survives the move: as a property the
reviewer derives, not one the implementer declares.

On iteration 2+ the leg receives the previous `review-code` findings as context
and authors the remediation; TDD still applies (failing test first for a
behavioural finding).

### 3.6 `/acs:review-code` *(new)*

The changeset review, modelled on Claude Code's own `/code-review`, in three
stages.

**Stage 1 — review.** Five lenses in parallel, read-only, running nothing:

| Lens | Judges | May read |
|---|---|---|
| A — Acceptance | requirement conformance, features | `requirements.md`, the plan, the diff |
| B — Changed-hunk defects | logic errors, security | **the diff and nothing else** |
| C — Contracts & architecture | API/data contract, design, plan conformance | `design.md`, architecture docs, the plan |
| D — History & regression | revert/hotfix patterns on touched lines | `git log --follow -p`, bounded lookback |
| E — Craft & scope | quality, standards, simplicity, scope creep | `standards/`, the diff |

Lens B is defined by what it may *not* read: it may not flag anything it cannot
establish from the diff alone. That constraint is what makes it a different
reviewer rather than a second copy of lens A.

Lens D runs on **every** run. On the evidence of MAR-583 it is the cheapest lens
and the highest-yield — it produced 4 of 9 blocking findings there, two of them
invisible in the diff.

**The reviewer scales itself.** `code-complex` spawned four verifier lenses
because a large changeset does not fit one reviewer's context — a real concern
that moves here along with the review. Lens B therefore fans out across the diff
when the diff warrants it: one instance per coherent slice, each still bound by
"the diff and nothing else". The trigger is measured from the changeset in front
of it, never passed in by `/acs:code` or by `ship.yaml`. Five lenses is the
shape; the number of *instances* is the reviewer's own call.

**…and scales down by the same rule.** A lens runs when its inputs exist.
Lens C judges conformance to the API contract and the design; on a run whose
`create-api-contract` recorded `no_surface_owed` and whose subject has no
`design.md`, it has nothing to judge and records that, exactly as the
contract step did. Lens B's fan-out on a twenty-line diff is one instance.
Adjudication is one validator per finding, and a small change yields few.
None of this reads the delivery path: the reviewer looks at what is in front
of it. What never scales down — on any path — is lenses A, B, D and E,
per-finding adjudication, and the gate. That is the floor §1.2 asked for, and
it is the same floor on `trivial` as on `complex`.

**Stage 2 — adjudication.** Every candidate finding gets one fresh-context
validator: given the finding, the requirement's intent, and read access to the
cited evidence — never the other findings, never which lens raised it.
Prompted to **refute**, defaulting to refuted when uncertain. `confirmed`
blocks; `refuted` is dropped with its reason recorded; `needs-context`
downgrades to advisory and is carried, never silently dropped.

Corroboration is **not** a filter. On MAR-583 iteration 1 all three blocking
findings were single-lens; counting agreement would have shipped a broken
changeset. Per-finding re-derivation is the filter.

**Stage 3 — the final gate.** Runs only when stage 2 leaves nothing blocking:

- **build** succeeds
- **lint** clean
- **full unit test suite** green
- **coverage ≥ 80%** (`settings.test_coverage_percent`, default 80)

The gate is the only place the full suite runs in the whole pipeline. It runs
last, exactly once per iteration that survives review, and a failure re-enters
the loop as a blocking finding. This is what makes `/acs:code`'s targeted-test
discipline safe: the guarantee is unconditional and terminal rather than buried
inside an iteration that may be discarded.

### 3.7 `/acs:create-e2e-tests` · 3.8 `/acs:run-e2e-tests`

Unchanged in role. Both **run on every run** and record an evidenced no-op
otherwise: `create-e2e-tests` when the plan declared no e2e impact,
`run-e2e-tests` when the repo has no e2e harness configured or there is nothing
to run. `run-e2e-tests` is the only place the e2e suite runs, and a failure
re-enters the `code`↔`review-code` loop as a blocking finding rather than
needing its own `on_fail:` wiring.

> **Open naming decision.** The request called step 6 `/tests`. Recommend
> keeping `run-e2e-tests`: step 6's final gate already runs the *unit* suite, so
> a skill called `/tests` that runs only e2e is the kind of name that costs a
> reader ten minutes. The deprecated `test` alias is removed either way.

### 3.9 `/acs:docs-sync`

Unchanged. Re-derives the doc delta from the diff itself rather than from any
upstream summary, and commits on the same branch.

### 3.10 `/acs:create-pr`

**Creates the branch.** Nothing earlier in the pipeline does.

Steps 3, 4 and 7 commit to whatever branch the session is already on. At
`create-pr`:

1. resolve the base branch (the repo default, or `--base`)
2. if `HEAD` is on the base branch, `git checkout -b <rendered-branch-name>` at
   `HEAD` — the commits come along
3. push the new branch and open the PR against the base
4. **reset the local base branch to its remote** so the work exists only on the
   PR branch

If `HEAD` is already on a non-base branch, that branch is used as-is and step 4
does not run.

> **This is the riskiest mechanical change in the redesign.** Committing to a
> checked-out `main` before a branch exists is safe only if step 4 is reliable.
> The hook enforcement in §5 exists partly for this: a pre-push guard refuses a
> push of the base branch itself.

---

## 4. State

Two machines — the **run** (the workflow's progress) and the **step** (one
skill's progress inside it) — both explicit, both durable, both resumable, and
both redesigned here rather than re-keyed. §4.1 says what exists today and why
it cannot hold a second workflow; §4.2–4.9 specify the replacement.

### 4.1 What exists today, and what is wrong with it

```
.acs/state-machine/<repo-id>/
  counters.json                    ticket id allocator
  tickets-index.json               every ticket
  metrics.json                     repo aggregates
  sessions/<checkout>.json         current-ticket pointer   ┐
  sessions/<checkout>-session.json                          │ five files per checkout,
  sessions/<checkout>-cost-cursor.json                      │ related by filename prefix
  sessions/<checkout>-cost-samples.jsonl                    │
  sessions/<checkout>-claude-version.json                   ┘
  <ticket-id>/                     THE PARTITION — a ticket id, nothing else
    ticket.json
    clarifications.json
    pipeline-state.json            workflow state: steps keyed by SKILL NAME, closed 18-name enum
    <skill>-state.json  × N        skill state: `skill` is a closed 33-name enum
    phases/<skill>/                artifacts: iter-1-execute.json, iter-1-execute-task.xml,
                                   iter-1-verify.md, iter-1-verdict.json, plan.md,
                                   plan-superseded-1.md, result.json, pr-body.md …
    .lock · lock-events.jsonl · active-agents/ · handoff-context.md
```

Six things are wrong with it, and none is fixable by renaming a directory:

1. **The partition is a ticket.** Nothing can run without one (§1.3).
2. **Two closed enums name the skills** — 18 in `pipeline-state.schema.json`,
   33 in `skill-state.schema.json` — and `acs.py start` / `acs.py finish` carry
   the same lists a third and fourth time as `argparse` choices. Adding a
   skill is four edits; adding a workflow is impossible.
3. **No file says which workflow is running**, at what version, or which run
   this is. `flow: ticket|product` is the only hint.
4. **`acs_lib/state.py` owns six unrelated things** — skill state, pipeline
   state, tickets, counters, the index and locks — in 25 public functions,
   because they all happened to live in the same directory.
5. **Iteration is a filename prefix.** `iter-1-execute-superseded-1.json` is
   what the scheme produces under pressure; the audit trail of a step is a
   glob, and the "current" artifact is whichever file sorts last.
6. **Two statuses are not states.** `skipped` records a workflow predicate's
   answer (§2), and `handed_off` records *why* a step stopped, not *that* it
   stopped.

### 4.2 Layout

```
.acs/state-machine/<repo-id>/
  counters.json                    id allocation — tickets, and runs when they share the allocator
  tickets-index.json               every ticket (unchanged)
  runs-index.json                  every run: id, workflow, subject, status, started/ended
  metrics.json                     repo aggregates (unchanged)
  tickets/<ticket-id>/ticket.json  only when settings.artifacts.tickets_path is null
  sessions/<checkout-id>/          one directory per checkout, not five prefixed files
    pointer.json                   current run + step  (was: current ticket + skill)
    session.json · cost.jsonl · runtime.json
  runs/<run-id>/
    run.json                       THE RUN MACHINE                             (§4.3)
    subject/                       what this run is about: ticket.json | prompt.md | document
    requirements.md                step 1's artifact, promoted: every later step reads it
    clarifications.json            the ledger, run-scoped
    lock.json · lock-events.jsonl  the lock protocol, unchanged, relocated
    agents/ · handoff-context.md   runtime scratch, unchanged, relocated
    steps/<skill>/
      state.json                   THE STEP MACHINE                            (§4.4)
      result.json                  the step's final result document — the post-hook's input
      plan.md · api-contract.md · test-cases.md · pr-body.md …   CURRENT artifacts
      iter-<n>/                    the AUDIT TRAIL: one directory per iteration
        plan.md · execute.json · execute-<k>.json · task.json
        lens-<A..E>.md · adjudication.json · gate.json · verdict.json
```

**The run id is the primary key.** A ticket id, when supplied, is the run's
*subject*, recorded in `run.json` and copied into `subject/` — never the
partition name. A run started from a prompt records the prompt; from a
document, the document's path and hash.

**Steps are keyed by skill name.** With no `id:` in `ship.yaml` (§2.1) the
step *is* the skill, and the state layer says so: `steps/review-code/`, not
`steps/<some-id>/`. A workflow that wanted the same skill twice would need ids
back; no workflow this plan can see wants that.

**The step root is the present; `iter-<n>/` is the past.** `plan.md` at the
step root is *the* plan; `iter-1/plan.md` and `iter-2/plan.md` are the plans
there were. A reader who wants the current artifact reads the root; a reader
who wants the history lists the directories. The prefix scheme's
`plan-superseded-1.md` and the `phases/code/plan.md` approval mirror both
disappear — there is one plan, at `steps/create-impl-plan/plan.md`, and
`plan_sha256` hashes it.

For `code` and `review-code`, `n` is the workflow loop's iteration (§4.3), so
`steps/code/iter-2/` and `steps/review-code/iter-2/` are the same round. For
a skill with its own internal cycle (`docs-sync`, `create-pr`, the design
skills), `n` is that cycle's iteration. Either way: *the n-th time this step
ran its cycle*.

### 4.3 The run machine — `run.json`

```jsonc
{
  "run_id": "20260919-a1b2c3",
  "workflow": "ship",                    // the file name, workflows/ship.yaml
  "workflow_version": 3,
  "subject": { "kind": "ticket", "ticket_id": "MAR-590" },   // or kind: prompt | document
  "status": "in_progress",
  "cursor": "review-code",               // the first step not completed
  "steps": {
    "analyze-requirements": { "status": "completed", "started_at": "…", "ended_at": "…", "summary": "…" },
    "create-api-contract":  { "status": "completed", "outcome": "no_surface_owed" },
    "code":                 { "status": "completed", "iteration": 2, "leg": "code-standard" },
    "review-code":          { "status": "in_progress", "iteration": 2 }
  },
  "loops": { "review-code": { "iteration": 2, "max": 3 } },
  "totals": { "…": "cost, tokens, wall time — unchanged" }
}
```

**Run states** — four, one terminal pair and one human escape hatch:

```
              ┌──────────────┐  last step completed   ┌───────────┐
  created ──▶ │ in_progress  │ ─────────────────────▶ │ completed │
              └──────┬───────┘                        └───────────┘
                     │ a step failed · loop exhausted  ┌───────────┐
                     ├──────────────────────────────▶ │  failed   │
                     │ acs run abandon (a human)       ├───────────┤
                     └──────────────────────────────▶ │ abandoned │
                                                      └───────────┘
```

**Step states** — four. A step absent from `steps` is pending.

```
  (absent) ──▶ in_progress ──▶ completed          with an optional `outcome` (§4.5)
                    │
                    ├─────────▶ failed             could not do its work; the run fails
                    │
                    └─────────▶ interrupted        resumable; `stop_reason` says why:
                                                   session_end · needs_input · context_pressure
```

`skipped` is gone (§2). `handed_off` is gone: it named a reason, and the
reason now lives in `stop_reason` on a single resumable state.

**Every transition has exactly one writer, and it is never an agent:**

| Transition | Writer | Fires on |
|---|---|---|
| run created | `acs run new` | the first step's pre-hook finds no run for this checkout |
| step → `in_progress` | `acs step start` | `PreToolUse(Skill)` of that skill |
| step → `completed` with a no-op `outcome` | `acs step finish --no-op` | the skill's pre-hook finds nothing owed in `## Contract`; no coordinator runs |
| step → `completed` / `failed` | `acs step finish`, from `result.json` | the skill's post-hook |
| step → `interrupted` | `acs step finish --interrupted` | `Stop` on an abandoned step; `SessionEnd` |
| `loops.<step>.iteration` += 1 | `acs step finish` | `review-code` finishes with `outcome: blocking_findings` |
| `cursor` recomputed | every `acs step finish` | — |
| run → `completed` | `acs step finish` | the last step of the workflow completes |
| run → `failed` | `acs step finish` | a step fails, or a loop exhausts |
| run → `abandoned` | `acs run abandon` | a human |

**Invariants**, checked by `acs run check` and by every pre-hook before it
allows a transition:

- **I1** at most one step is `in_progress` per run
- **I2** `cursor` is the first step in workflow order that is not `completed`;
  the `in_progress` step, when there is one, is the cursor
- **I3** a `completed` step has a `result.json`, and its `state.json` agrees
- **I4** `loops.<step>.iteration ≤ max`
- **I5** every key of `steps` is a step of the resolved workflow, and every
  `leg` is a leg of that step's skill in `workflows/phases.yaml`

I5 is where the closed enums went: the *workflow* validates step names, the
*registry* validates skill and leg names, and the JSON schema validates shape.
Adding a workflow is a YAML file; adding a skill is a registry entry; neither
touches a schema.

### 4.4 The step machine — `steps/<skill>/state.json`

The current shape is sound and is kept: a `states` object, `findings`,
`errors`, and one record per invocation carrying session id, transcript path,
checkout id, tokens, cost, role/model usage, guard events, gate enforcement,
status and stop reason. Four changes:

1. **`runs[]` becomes `invocations[]`.** Once the partition is `runs/<run-id>/`,
   a `runs` array inside a step's state means the wrong thing. An invocation
   is one session's attempt at this step.
2. **`ticket_id` becomes `run_id`.**
3. **`skill` is validated against the registry, not an enum.** The 33-name
   list leaves the schema.
4. **The `states` keys are declared per skill.** Today one central schema
   lists every skill's `states` keys — `verifier_passed`, `plan_approved`,
   `file_map`, `pr`, `merged`, `readiness`, sixteen of them. Each skill's
   directory gains `state.schema.json`, a fragment declaring *its* `states`
   keys and *its* `outcome` vocabulary; the central `step-state.schema.json`
   validates only the envelope. This is the same move as §4.3's I5: a new
   skill is a directory, not a central edit. It is also the mechanism by
   which a skill is standalone in state as well as in invocation.

**Derived, never asserted** (MAR-523, MAR-527) carries over unchanged and is
extended: `verifier_passed` is computed by the post-hook from
`review-code`'s `verdict.json`; `tests` from the gate's own run; `outcome`
is read from `result.json` and checked against the fragment. A skill that
writes a value the post-hook derives is overwritten, and the disagreement is
recorded in `errors`.

### 4.5 `outcome` — a closed vocabulary per step

`outcome` is declared in the skill's `state.schema.json` fragment and
validated by its post-hook. A step with only one way to complete has no
`outcome` at all. The steps with more than one:

| Step | `outcome` values |
|---|---|
| `create-api-contract` | `contract_written` · `no_surface_owed` |
| `create-test-docs` | `cases_written` · `no_cases_owed` |
| `code` | `implemented` — always with `leg` |
| `review-code` | `passed` · `blocking_findings` (re-enters the loop) · `exhausted` (cap reached; run fails) |
| `create-e2e-tests` | `tests_written` · `no_e2e_owed` |
| `run-e2e-tests` | `passed` · `no_harness` · `nothing_to_run` |

A failure is not an outcome. A step that could not do its work records
`status: failed` with an error, never a completed step with a sad `outcome`;
the distinction is what keeps "nothing was owed" from being confused with
"something went wrong".

### 4.6 Schemas

Fifteen JSON schemas and one XSD today; the table is every one of them.

| Today | v0.5.0 | Change |
|---|---|---|
| `pipeline-state.schema.json` | `run.schema.json` | open `steps`; `cursor`, `loops`, `subject`, `workflow`, `workflow_version`; no `flow`, no `delivery_path` |
| `skill-state.schema.json` | `step-state.schema.json` + `skills/<skill>/state.schema.json` | envelope centrally, `states` and `outcome` per skill; `runs[]` → `invocations[]`; no `skill` enum |
| `ship-workflow.schema.json` | `workflow.schema.json` | `steps` is a list of names; `loops`; **rejects** every v2 key §2.1 removed |
| `session-pointer.schema.json` | same | `ticket_id`, `skill` → `run_id`, `step` |
| `clarifications.schema.json` | same | `ticket_id` → `run_id` |
| `verdict.schema.json` | same | owned by `review-code`; gains `iteration` |
| — | `result.schema.json` | **new** — the step result document, today validated ad hoc by `acs phase validate` |
| `ticket.schema.json`, `tickets-index.schema.json`, `counters.schema.json`, `lock.schema.json`, `lock-events.schema.json`, `metrics.schema.json`, `phases.schema.json`, `settings.schema.json` | same | unchanged (settings loses the removed keys) |
| `acs-messages.xsd` | — | removed (§6) |

### 4.7 The kernel — `acs_lib`

The rule is **one module per machine, one machine per module**. `state.py`'s
six concerns become five modules with one concern each; `workflow.py` loses
everything §2.1 removed.

| Module | Owns | Today |
|---|---|---|
| `run.py` | `run.json`: create, transition, cursor, loops, invariants I1–I5 | half of `state.py`, `workflow.next_steps`, `pending_needs` |
| `step.py` | `state.json`: invocations, `states`, `outcome`, findings, errors | the other half of `state.py` |
| `lock.py` | the lock and its ledger, unchanged in protocol | `state.py` |
| `sessions.py` | `sessions/<checkout-id>/` | scattered across `repo.py`, `metrics.py`, `state.py` |
| `tickets.py` | `ticket.json` and `tickets-index.json` | `state.py` + the ticket half of `artifacts.py` |
| `workflow.py` | load, validate, `loops`, the step list | minus `delivery_*`, `per_path`, `is_path_dependent`, `step_skills`, every predicate, `next_steps` |
| `derive.py` | unchanged role; reads `iter-<n>/` directories instead of globbing prefixes | — |
| `lifecycle.py` | unchanged role; writes under `runs/<run-id>/` | — |
| `gates.py` | `build_context`, `run_pre`, `run_post`; reads the cursor, not `needs` | minus the ready-set logic |

### 4.8 The CLI

`acs.py start` and `acs.py finish` carry the skill list as `argparse`
choices, which is the closed enum in a fourth place. They are replaced, and
the run gets a verb of its own:

| v0.5.0 | Replaces | Notes |
|---|---|---|
| `acs run new \| show \| next \| check \| abandon` | `acs workflow next`; nothing for the rest | `next` is the cursor; `check` is I1–I5 |
| `acs step start \| finish \| show --run <id> --step <name>` | `acs start`, `acs finish` | `--step` validated against the resolved workflow, not an enum |
| `acs result validate` | `acs phase validate` | "phase" meant three things; this one is the result document |
| `acs workflow show \| validate` | same | `next` moved to `acs run` |
| `acs plan path` | `acs path` | the path is read from the plan's `## Contract` block |
| `acs lock`, `acs ticket`, `acs verdict`, `acs filemap`, `acs guard`, `acs context` | same | unchanged |
| — | `acs artifacts migrate` | removed: there is no migration |

### 4.9 Resumption and concurrency

A run resumes from `run.json` alone. `/acs:ship <run-id>` re-reads it, asks
`acs run next` for the cursor, and continues. A step recorded `in_progress`
or `interrupted` is re-run; its skill-start reconciles recorded state against
reality (the working tree, the branch, the artifacts on disk) rather than
trusting it, exactly as today.

The lock protocol is unchanged — re-entrant for the same checkout, fail-closed
for any other, force-release audited to the ledger — and moves from the ticket
partition to the run partition. Two runs on the same subject are two
partitions and two locks; the second is refused by `acs run new` unless the
first is terminal.

---

## 5. Enforcement

Every skill keeps hook-backed gating; prose is never the enforcement mechanism.

| Event | Enforces |
|---|---|
| `PreToolUse(Skill)` | the step is at or behind `run.json`'s cursor |
| `PreToolUse(Skill)` — new | records a no-op completion from `## Contract` and refuses the invocation, so nothing is owed costs nothing (§2.2) |
| `PreToolUse(Write\|Edit\|MultiEdit)` | the executor stays inside the plan's file map |
| `PreToolUse(Write\|Edit\|Bash)` — new | **refuses every mutation while `create-impl-plan` is the active step** (§3.2's read-only guarantee) |
| `PreToolUse(Skill)` — new | refuses `code` when the plan's approval is absent or its `plan_sha256` is stale |
| `SubagentStart\|Stop` | the phase artifact exists and its verdict holds together |
| `Stop` / `SessionEnd` | step → `interrupted` with its `stop_reason`, lock release |
| every pre-hook — new | `acs run check`: invariants I1–I5 (§4.3) hold before any transition |
| `PreToolUse(Bash)` — new | refuses a `git push` of the base branch (§3.10) |

Two properties carry over unchanged because they are load-bearing and were
expensive to get right:

- **Verdicts are derived, never asserted.** `review-code`'s pass/fail is
  computed by the post-hook from the verdict file. A skill claiming to have
  passed does not pass.
- **Gate evidence is recorded fail-open.** A run that cannot confirm the hooks
  fired reports itself degraded rather than pretending, and never blocks on the
  absence of its own evidence.

---

## 6. Removals

No compatibility shims. These go in the same release.

| Removed | Because |
|---|---|
| the verifier inside `/acs:code` | moved to `/acs:review-code`, which every path now gets |
| the legs' per-path verifier shape and iteration ceiling | review properties; they leave with the review (§3.5) |
| `needs:`, `max_parallel`, `exclusive`, `on_fail:`, `boundary:` | the written order and one `loop:` (§2.1) |
| `when:` / `paths:` / `requires:` predicates | each skill decides for itself and records why (§2.1) |
| `delivery:` block in `ship.yaml` | the path is recorded on the plan, not configured on the workflow |
| `status: skipped` | replaced by `completed` + an `outcome` the skill wrote |
| `status: handed_off` | a reason, not a state: `interrupted` + `stop_reason` (§4.3) |
| `id:`, `name:`, `stop_after:` in `ship.yaml` | the skill name, the file name, the end of the list |
| the 18- and 33-name skill enums, and the `argparse` copies in `acs start` / `acs finish` | the workflow and the registry validate names (§4.3 I5) |
| `acs start`, `acs finish`, `acs phase validate`, `acs workflow next`, `acs artifacts migrate` | `acs step`, `acs result validate`, `acs run next`; no migration (§4.8) |
| the `iter-<n>-*` filename-prefix scheme and the `phases/code/plan.md` approval mirror | `iter-<n>/` directories; one plan (§4.2) |
| `test` (alias) | ambiguous; `run-e2e-tests` is the skill |
| XML messaging: `validate_xml.py`, `acs-messages.xsd`, `*-task.xml` snapshots | phase results are JSON, validated in the hook |
| `flow: ticket\|product` | replaced by `workflow` + `workflow_version` |
| ticket-keyed partitions | replaced by run-keyed |
| `phases/` artifact level | redundant under step directories |

**Skill count: 32 → 32.** One skill is added (`review-code`), one removed (the
`test` alias), one renamed (`analyze-ticket` → `analyze-requirements`). The four
delivery-path legs stay. This redesign is not a surface reduction — it is a
re-cut of where the decisions live, and the surface is the same size on the
other side of it.

---

## 7. What is deliberately kept

Named explicitly so a "from scratch" reading does not discard them:

- the **clarification ledger** and its `--source assumption` discipline
- the **lock protocol**
- **gate evidence** (MAR-583)
- **derived verdicts** (MAR-523, MAR-527)
- the **file-map guard** and its denial records
- **cost / token / session attribution** in `runs[]`
- the **four delivery paths and their `code-*` legs** — what changes is where the
  path is recorded (the plan, not `ship.yaml`) and who dispatches on it
  (`/acs:code`, not the workflow), never that the path exists
- **plan approval** bound to `plan_sha256`, written only by `plan-approval.py`
  and never by an agent
- `workflows/phases.yaml` as the single, non-overridable skill registry feeding
  the workflow schema, the README table, INTERNALS and metrics grouping
- the split where the **plugin owns the registry and the consumer owns the
  pipeline** — this is what makes "add more workflows" safe

---

## 8. Refactor plan

Seven phases, each landing independently and leaving the tree green. There is
**no interim release**: `[Unreleased]` accumulates through P1–P6 and the
v0.5.0 cut happens once, at the end, against the finished tree.

**This plan is executed directly, not through the acs pipeline.** The pipeline
cannot rebuild its own state machine while running on it, and every phase
below changes something `/acs:ship` or `/acs:code` depends on. The phases are
ordinary branches and PRs, labelled `acs-exempt`; this document is the plan of
record and there are no tracker tickets for it.

**P1 — the state machine.** All of §4: the run partition and `runs-index.json`;
`run.json` with its four run states, four step states, single-writer
transitions and invariants I1–I5; `state.json` with `invocations[]`, `run_id`
and the per-skill `state.schema.json` fragments; `iter-<n>/` directories;
`sessions/<checkout-id>/`; the schema table in §4.6; `acs_lib` split into
`run.py` / `step.py` / `lock.py` / `sessions.py` / `tickets.py`; `acs run` and
`acs step` replacing `acs start` / `acs finish` / `acs workflow next`. The two
closed skill enums and their `argparse` copies go here. Foundation for
everything else. Lands against the *current* `ship.yaml` v2 — P1 does not
change the workflow, only what records its progress — so the tree stays green
between P1 and P2a.

**P2a — workflow engine.** `ship.yaml` version 3: the flat step list, the
`loop:` construct, `cursor` in `run.json`, and a workflow schema that
**rejects** `needs:` / `when:` / `paths:` / `requires:` / `delivery:` /
`max_parallel` / `exclusive:` / `on_fail:` / `boundary:` / `id:` / `name:` /
`stop_after:`. `/acs:ship` becomes a pure orchestrator over `acs run next`. Lands with an ADR — *Workflows
carry no conditions* — because it is the rule every future workflow is held
to, and ADR-0095 (which put the paths *in* the workflow) needs a successor
that says why they came back out.

**P2b — re-home the predicates.** Each removed predicate lands on the skill
that can evaluate it from its own inputs (§2.1's table): `create-api-contract`,
`create-test-docs`, `create-e2e-tests` and `run-e2e-tests` each gain their
applicability check **in their pre-hook** (§2.2), their evidenced no-op
artifact and their `outcome` vocabulary (§4.5); `/acs:code` gains the leg dispatch the per-path `skill:`
mapping used to do; `/acs:create-impl-plan` gains the `## Contract` block
(§3.2) that records the delivery path and the "owed" statements. Five skills,
each a small change, none of which touches the engine.

**P3 — split the review out of `/acs:code`.** Extract the verifier into
`/acs:review-code`: five lenses, per-finding adjudication, final gate (build,
lint, full suite, coverage ≥80%), and the self-scaling lens-B fan-out that
replaces `code-complex`'s four-lens spawn. The four legs **stay** and keep their
executor and plan-approval rules; what leaves them is the verifier and the
iteration ceiling. The largest phase and the one carrying the most risk.

**P4 — `/acs:analyze-requirements` and plan mode.** Rename `analyze-ticket`,
accept prompt and document inputs, make the ticket id optional throughout.
Re-shape `/acs:create-impl-plan` to §3.2: read-only until approved (with the
hook that enforces it), a plan written for one human read, approval bound to
`plan_sha256`, and the delivery path recorded on the plan.

**P5 — `/acs:create-pr` owns the branch.** Branch creation moves to the last
step; add the base-branch push guard.

**P6 — removals and doc sweep.** Delete what §6 lists, remove the XML
machinery, supersede the remaining ADRs the redesign overturns (ADR-0067's
merge rule relocates; the `/acs:code` triad chain), rewrite INTERNALS.

### Ordering constraints

- P1 precedes everything — every other phase writes state.
- P2a and P2b land **together or P2b first**: deleting `when:` from the
  workflow before the skill has its own check silently makes that skill run
  unconditionally, and deleting `delivery:` before the plan records the path
  leaves `/acs:code` with nothing to dispatch on.
- P2a precedes P3: the loop must live in the workflow before the review can
  leave `/acs:code`, and the legs cannot lose their iteration ceiling until
  something else owns it.
- P4 depends on P2b's `## Contract` block and builds the rest of plan mode on
  top of it.
- P5 is independent of P3/P4 and can run in parallel.
- P6 lands last; deleting a skill before its replacement ships breaks the tree.

### The release gate

The paid eval gate runs **once, after P6**, against the finished tree. Running
it earlier measures a build that is about to be replaced, and the measurement
would be void before it was read.

Two consequences for the eval dataset, both expected:

- The **build digest** moves with every phase. It is not a stable precondition
  during P1–P6; re-derive it at gate time and name the tree by what it is.
- The **skill-surface fingerprint** (`60a7c34b59f402c0`) **will** move. The
  count is unchanged at 32, but the set is not: `review-code` is added, the
  `test` alias removed, `analyze-ticket` renamed, and every `code-*` leg's
  frontmatter description is rewritten by P3. The routing baseline and
  `dataset/manifest.json`'s `recorded_against_fingerprint` are therefore
  invalidated by design, and both are re-recorded as part of the gate rather
  than treated as a regression. The 43-probe routing set needs editing in P6 to
  match the new skill names — including probes that must now route to
  `review-code` rather than to a `code-*` leg.

### Open decisions

1. **Step 6's name** — `run-e2e-tests` (recommended) or `/tests`.
2. **Coverage target** — this document takes 80% from the request;
   `.acs/settings.json` currently sets 90. Lowering it is a policy change worth
   stating deliberately rather than inheriting from a redesign.
3. **Run id format** — `YYYYMMDD-<6 hex>`, or keep the `MAR-N` allocator and let
   ticketless runs draw from it too.
4. **The integration executor** — §3.5 gives `code-complex` a post-partition
   integration pass, because removing the four-lens verifier from that leg would
   otherwise leave `standard` and `complex` executing identically. It is the
   one genuinely *new* mechanism in this redesign rather than a relocation, so
   it is the one most worth a second opinion. The alternative is to collapse the
   two legs and let the plan say `standard` for both.
5. **`runs[]` → `invocations[]`** in step state (§4.4). Forced by naming the
   partition `runs/`; the alternative is to name the partition something else
   (`jobs/`? `executions/`?) and keep `runs[]`. Either way one of them moves.
6. **Wall-clock cost of the flat list** — `docs-sync` no longer runs beside the
   e2e pair. Accepted here as the price of a workflow with no graph; measure it
   at the gate and reconsider only if it shows up.
