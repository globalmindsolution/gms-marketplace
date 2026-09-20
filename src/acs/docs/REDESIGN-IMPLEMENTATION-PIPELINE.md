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
a schema edit; a workflow cannot use a skill twice; two workflows cannot share
a skill; the same workflow cannot run twice on one subject. `ship.yaml` already
distinguishes a step's `id` from its `skill` — the state layer throws the `id`
away.

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
the workflow — it runs, reads the plan, records "no API surface in this plan"
and completes. The same holds for `create-test-docs` and `create-e2e-tests`.
The audit trail gains a step that says *why* nothing was owed, which a `skipped`
status never carried.

```
 1  analyze-requirements   clarify the requirement from a ticket, a prompt or a document
 2  create-impl-plan       the implementation plan and its test strategy
 3  create-api-contract    the API/data contract, when the plan declares that surface
 4  create-test-docs       test-cases.md — the TC-n set code and review both trace to
 5  code                   implement with TDD — targeted tests only
 6  review-code            five-lens review + adjudication + final gate    ← loops with 5, cap 3
 7  create-e2e-tests       author the e2e tests the plan declared
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
legible by reading it top to bottom, and `acs workflow next` is "the first step
not yet completed" rather than a graph traversal.

### 2.1 `workflows/ship.yaml` (version 3)

```yaml
version: 3
name: ship
stop_after: create-pr

steps:
  - id: analyze-requirements
    skill: analyze-requirements
  - id: create-impl-plan
    skill: create-impl-plan
  - id: create-api-contract
    skill: create-api-contract
  - id: create-test-docs
    skill: create-test-docs
  - id: code
    skill: code
  - id: review-code
    skill: review-code
    loop:
      back_to: code           # on blocking findings, re-enter at `code`
      max_iterations: 3       # counts code→review-code rounds
      on_exhausted: fail      # never "pass with findings"
  - id: create-e2e-tests
    skill: create-e2e-tests
  - id: run-e2e-tests
    skill: run-e2e-tests
  - id: docs-sync
    skill: docs-sync
  - id: create-pr
    skill: create-pr
```

That is the entire file. Four keys at the top level, `id` and `skill` per step,
and one `loop:`.

**`loop:` is the only construct, and it is not a condition.** It tests nothing
about the change — it declares that two steps form a cycle and how many times.
That cannot live inside a skill, because it spans two of them: today the
execute↔verify loop lives *inside* `/acs:code`, which is precisely why the
review cannot be a separate skill. Moving the loop into the workflow is what
lets `/acs:review-code` be standalone, and it is the crux of this redesign.

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
| `on_fail: relay_to` | the `loop:` above, for the one loop there is |

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

### 3.3 `/acs:create-api-contract`

Kept as its own step rather than folded into the plan. **It runs on every run.**
It reads the plan, decides for itself whether the change has an API or data
surface, and when it does not it records a completed step whose artifact says
so — the surfaces it checked, and why none is owed. That record is worth more
than the `skipped` it replaces: `skipped` never distinguished *the plan says
nothing is owed* from *the workflow never asked*.

The no-op is cheap — one read of the plan and one short artifact — and it is
what makes `/acs:create-api-contract` answer the same way whether `/acs:ship`
invoked it or a developer did.

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

Two state machines, both explicit, both durable, both resumable.

### 4.1 Layout

```
.acs/state-machine/<repo-id>/
  counters.json                       # id allocation
  index.json                          # every run, its subject and status
  runs/<run-id>/
    run.json                          # WORKFLOW state
    requirements.md                   # step 1's artifact, the run's authority
    clarifications.json               # ledger, run-scoped
    inputs/                           # the prompt / document / ticket ref given
    steps/<step-id>/
      state.json                      # SKILL state
      <artifacts>                     # plan.md, iter-N-*.json, verdict.json, …
```

**The run id replaces the ticket id as the primary key.** A ticket id, when
supplied, is recorded as a *label* on the run (`run.json` → `subject`), not as
the partition name. Runs without a ticket get a generated id
(`YYYYMMDD-<6 hex>`).

The `phases/` directory level is **removed**. Once a step is a directory,
everything inside it is that step's phase output by construction, and `phases`
collided with `workflows/phases.yaml`, which means something unrelated (the
skill registry, grouped by lifecycle phase).

### 4.2 Workflow state — `run.json`

```jsonc
{
  "run_id": "20260919-a1b2c3",
  "workflow": "ship",
  "workflow_version": 3,
  "subject": { "kind": "prompt", "ticket_id": null, "text": "…" },
  "status": "in_progress",
  "cursor": "review-code",
  "steps": {
    "analyze-requirements": { "status": "completed", "started_at": "…", "ended_at": "…" },
    "create-api-contract":  { "status": "completed", "outcome": "no_surface_owed" },
    "code":                 { "status": "completed", "iteration": 2, "leg": "code-standard" },
    "review-code":          { "status": "in_progress", "iteration": 2 }
  },
  "loop": { "review-code": { "iterations": 2, "max": 3 } },
  "totals": { "…": "cost, tokens, wall time" }
}
```

`steps` is keyed by the workflow's **step id** and is **open** — no enum. Step
names are validated against the *resolved workflow document*, by
`acs workflow validate`, not against a literal in a JSON schema. The schema
validates shape; the workflow validates names. This is what makes a new
workflow a YAML file rather than a schema edit, and it removes the
hand-maintained 18-name enum that duplicates `workflows/phases.yaml`.

Two consequences of the flat step list land here. **`cursor` replaces the
ready-set**: with no `needs:` graph, `acs workflow next` returns the first step
whose status is not `completed`, and the cursor is that answer cached. And
**`status: skipped` is gone from the vocabulary** — a step either completed
(possibly with an `outcome` recording that nothing was owed) or it did not run
yet. `outcome` is the skill's word, written into its own artifact and mirrored
here; the workflow never infers it.

### 4.3 Skill state — `steps/<step-id>/state.json`

Keeps today's shape, which is sound: `states`, `findings`, `errors`, and a
`runs[]` array carrying per-invocation session id, transcript path, checkout id,
tokens, cost, role/model usage, guard events, gate enforcement, status and stop
reason. Only its location and key change.

### 4.4 Resumption

A run resumes from `run.json` alone. `/acs:ship <run-id>` re-reads the ledger,
asks `acs workflow next` for the ready steps, and continues. A step recorded
`in_progress`, `failed` or `interrupted` is simply re-run; the step's own
skill-start reconciles recorded state against reality rather than trusting it.

---

## 5. Enforcement

Every skill keeps hook-backed gating; prose is never the enforcement mechanism.

| Event | Enforces |
|---|---|
| `PreToolUse(Skill)` | the step is at or behind `run.json`'s cursor |
| `PreToolUse(Write\|Edit\|MultiEdit)` | the executor stays inside the plan's file map |
| `PreToolUse(Write\|Edit\|Bash)` — new | **refuses every mutation while `create-impl-plan` is the active step** (§3.2's read-only guarantee) |
| `PreToolUse(Skill)` — new | refuses `code` when the plan's approval is absent or its `plan_sha256` is stale |
| `SubagentStart\|Stop` | the phase artifact exists and its verdict holds together |
| `Stop` / `SessionEnd` | run bookkeeping, lock release |
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

Six phases. Each is an epic; each lands independently and leaves the tree green.
There is **no interim release**: `[Unreleased]` accumulates through P1–P6 and
the v0.5.0 cut happens once, at the end, against the finished tree.

**P1 — state machine re-key.** Run ids, `run.json`, step-id keying, the open
`steps` object, name validation moved from schema to `acs workflow validate`,
`phases/` level removed. Foundation for everything else; no user-visible
behaviour change beyond the layout.

**P2 — workflow engine.** `ship.yaml` version 3: the flat step list, the
`loop:` construct, and the removal of `needs:` / `when:` / `paths:` /
`requires:` / `delivery:` / `max_parallel` / `on_fail:` / `boundary:`. Each
removed predicate is re-homed in the same phase (§2.1's table) — in particular
`create-api-contract`, `create-test-docs`, `create-e2e-tests` and
`run-e2e-tests` each gain their own applicability check and evidenced-no-op
artifact, and `/acs:code` gains the leg dispatch that the per-path `skill:`
mapping used to do. `/acs:ship` becomes a pure orchestrator over
`acs workflow next`.

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

**P6 — removals and doc sweep.** Delete the skills in §6, remove the XML
machinery, supersede the ADRs the redesign overturns, rewrite INTERNALS.

### Ordering constraints

- P1 precedes everything — every other phase writes state.
- P2 precedes P3: the loop must live in the workflow before the review can leave
  `/acs:code`, and the legs cannot lose their iteration ceiling until something
  else owns it.
- P4's plan-mode re-shape precedes nothing and blocks nothing, but the delivery
  path must be recorded on the plan before P2 can delete the `delivery:` block —
  so that one line of P4 lands inside P2.
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
5. **Wall-clock cost of the flat list** — `docs-sync` no longer runs beside the
   e2e pair. Accepted here as the price of a workflow with no graph; measure it
   at the gate and reconsider only if it shows up.
