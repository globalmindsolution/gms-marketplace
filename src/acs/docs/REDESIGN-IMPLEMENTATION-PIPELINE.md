# Redesign: the implementation pipeline (v0.6.0)

**Status**: Proposed · **Date**: 2026-09-19 · **Scope**: implementation skills only

This document specifies a from-scratch redesign of acs's **implementation**
half — the skills `/acs:ship` orchestrates between a settled requirement and an
open PR. The **design** skills (`create-prd`, `create-requirements`,
`create-architecture`, `create-docs`, `project`, `create-ticket`,
`create-design`) are out of scope and keep their current shape.

It is a **breaking redesign with no backward-compatibility layer**. State
written by v0.5.x is not read by v0.6.0; there is no dual-read release and no
migration of in-flight runs. Finish or abandon open runs before upgrading.

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

**4. Redundant surface.** 32 skills ship, of which four are delivery-path legs
of one skill, one is a deprecated alias, and two author documents that the
implementation plan already contains.

---

## 2. The pipeline

Eight steps, declared in `workflows/ship.yaml`. `/acs:ship` is a **pure
orchestrator**: it reads the workflow, resolves which steps are ready, invokes
them, and records state. It contains no step logic of its own.

```
1  analyze-requirements   clarify the requirement from a ticket, a prompt or a document
2  create-impl-plan       the implementation plan and its test strategy
3  code                   implement with TDD — targeted tests only
4  review-code            five-lens review + adjudication + final gate     ← loops with 3, cap 3
5  create-e2e-tests       author the e2e tests the plan declared
6  run-e2e-tests          run them
7  docs-sync              re-derive and apply the doc deltas
8  create-pr              create the branch, push, open the PR
```

Steps 3 and 4 form a loop with a **cap of 3 iterations**. Steps 6 and 7 have no
dependency on each other and run in parallel. The run stops at `create-pr`;
merging stays a human action through `/acs:merge-pr`.

### 2.1 `workflows/ship.yaml` (version 3)

```yaml
version: 3
name: ship
stop_after: create-pr
max_parallel: 2

steps:
  - id: analyze-requirements
    skill: analyze-requirements

  - id: create-impl-plan
    skill: create-impl-plan
    needs: [analyze-requirements]

  - id: code
    skill: code
    needs: [create-impl-plan]

  - id: review-code
    skill: review-code
    needs: [code]
    loop:
      back_to: code           # on blocking findings, re-enter this step
      max_iterations: 3       # counts code→review-code rounds
      on_exhausted: fail      # never "pass with findings"

  - id: create-e2e-tests
    skill: create-e2e-tests
    needs: [review-code]
    when: plan.e2e_impact     # the plan declares it; absent ⇒ skipped

  - id: run-e2e-tests
    skill: run-e2e-tests
    needs: [create-e2e-tests]

  - id: docs-sync
    skill: docs-sync
    needs: [review-code]      # parallel with the e2e pair

  - id: create-pr
    skill: create-pr
    needs: [run-e2e-tests, docs-sync]
```

**`loop:` is the one new construct.** Today the execute↔verify loop lives
*inside* `/acs:code`, which is why the review cannot be a separate skill. Moving
the loop into the workflow is what lets `/acs:review-code` be standalone, and it
is the crux of this redesign. A skipped step satisfies a `needs` edge, so a run
with no e2e impact reconverges on `create-pr` with no extra wiring.

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

Unchanged in role. Its input is now `requirements.md` rather than a ticket. It
absorbs two skills that are being removed:

- the **API/data contract** section replaces `/acs:create-api-contract`
- the **test strategy** section replaces `/acs:create-test-docs`, and is what
  `/acs:code` takes its targeted test set from and what `/acs:create-e2e-tests`
  reads for e2e impact

### 3.3 `/acs:code`

Implements the plan with TDD. **Targeted tests only** — the tests its change
touches, never the full suite. It has **no verifier**, and the four delivery
path legs (`code-trivial`, `code-small`, `code-standard`, `code-complex`) are
removed along with the delivery-path machinery that selected them.

On iteration 2+ it receives the previous `review-code` findings as context and
authors the remediation; TDD still applies (failing test first for a behavioural
finding).

### 3.4 `/acs:review-code` *(new)*

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

### 3.5 `/acs:create-e2e-tests` · 3.6 `/acs:run-e2e-tests`

Unchanged. `create-e2e-tests` runs only when the plan declared e2e impact.
`run-e2e-tests` is the only place the e2e suite runs.

> **Open naming decision.** The request called step 6 `/tests`. Recommend
> keeping `run-e2e-tests`: step 4's final gate already runs the *unit* suite, so
> a skill called `/tests` that runs only e2e is the kind of name that costs a
> reader ten minutes. The deprecated `test` alias is removed either way.

### 3.7 `/acs:docs-sync`

Unchanged. Re-derives the doc delta from the diff itself rather than from any
upstream summary, and commits on the same branch.

### 3.8 `/acs:create-pr`

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
  "steps": {
    "analyze-requirements": { "status": "completed", "started_at": "…", "ended_at": "…" },
    "code":                 { "status": "completed", "iteration": 2 },
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
| `PreToolUse(Skill)` | the step's predecessors are satisfied in `run.json` |
| `PreToolUse(Write\|Edit\|MultiEdit)` | the executor stays inside the plan's file map |
| `SubagentStart\|Stop` | the phase artifact exists and its verdict holds together |
| `Stop` / `SessionEnd` | run bookkeeping, lock release |
| `PreToolUse(Bash)` — new | refuses a `git push` of the base branch (§3.8) |

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
| `code-trivial`, `code-small`, `code-standard`, `code-complex` | the review is a separate skill now; the legs differed only by verify depth |
| delivery paths: `acs path`, `delivery:` in ship.yaml, `delivery_path` in state | nothing varies by path once the pipeline is fixed |
| `create-api-contract` | folded into the plan's API/data changes section |
| `create-test-docs` | folded into the plan's test strategy section |
| `test` (alias) | ambiguous; `run-e2e-tests` is the skill |
| the verifier inside `/acs:code` | moved to `/acs:review-code` |
| XML messaging: `validate_xml.py`, `acs-messages.xsd`, `*-task.xml` snapshots | phase results are JSON, validated in the hook |
| `flow: ticket\|product` | replaced by `workflow` + `workflow_version` |
| ticket-keyed partitions | replaced by run-keyed |
| `phases/` artifact level | redundant under step directories |

Skill count: **32 → 26**.

---

## 7. What is deliberately kept

Named explicitly so a "from scratch" reading does not discard them:

- the **clarification ledger** and its `--source assumption` discipline
- the **lock protocol**
- **gate evidence** (MAR-583)
- **derived verdicts** (MAR-523, MAR-527)
- the **file-map guard** and its denial records
- **cost / token / session attribution** in `runs[]`
- `workflows/phases.yaml` as the single, non-overridable skill registry feeding
  the workflow schema, the README table, INTERNALS and metrics grouping
- the split where the **plugin owns the registry and the consumer owns the
  pipeline** — this is what makes "add more workflows" safe

---

## 8. Refactor plan

Six phases. Each is an epic; each lands independently and leaves the tree green.

**P0 — cut v0.5.0 first.** The current release carries breaking changes already
(ship.yaml v2, the lane retirement, ticket-field removal). Land it, then break
cleanly at v0.6.0. Nothing in P1–P6 starts before this.

**P1 — state machine re-key.** Run ids, `run.json`, step-id keying, the open
`steps` object, name validation moved from schema to `acs workflow validate`,
`phases/` level removed. Foundation for everything else; no user-visible
behaviour change beyond the layout.

**P2 — workflow engine.** `ship.yaml` version 3, the `loop:` construct, delivery
paths removed. `/acs:ship` becomes a pure orchestrator over `acs workflow next`.

**P3 — split the review out of `/acs:code`.** Extract the verifier into
`/acs:review-code`: five lenses, adjudication, final gate (build, lint, full
suite, coverage ≥80%). Remove the four legs. The largest phase and the one
carrying the most risk.

**P4 — `/acs:analyze-requirements`.** Rename from `analyze-ticket`, accept
prompt and document inputs, make the ticket id optional throughout.

**P5 — `/acs:create-pr` owns the branch.** Branch creation moves to the last
step; add the base-branch push guard.

**P6 — removals and doc sweep.** Delete the skills in §6, remove the XML
machinery, supersede the ADRs the redesign overturns, rewrite INTERNALS.

### Ordering constraints

- P1 precedes everything — every other phase writes state.
- P2 precedes P3: the loop must live in the workflow before the review can leave
  `/acs:code`.
- P5 is independent of P3/P4 and can run in parallel.
- P6 lands last; deleting a skill before its replacement ships breaks the tree.

### Open decisions

1. **Step 6's name** — `run-e2e-tests` (recommended) or `/tests`.
2. **Coverage target** — this document takes 80% from the request;
   `.acs/settings.json` currently sets 90. Lowering it is a policy change worth
   stating deliberately rather than inheriting from a redesign.
3. **Run id format** — `YYYYMMDD-<6 hex>`, or keep the `MAR-N` allocator and let
   ticketless runs draw from it too.
