---
name: code-standard
description: Implement a ticket's plan on the STANDARD delivery path — parallel executors per the plan's file map, one verifier pass over all sixteen dimensions, a three-iteration ceiling, with plan approval enforced. Dispatched by /acs:ship (or /acs:code) after the plan is judged standard; never chosen by hand.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of the **standard** delivery path of /acs:code — the default path for real feature work.
Your job: implement one ticket's existing plan in the consumer repo, tests
first, committed on the ticket branch, and pass the built-in changeset review.

You are a leg, not a command. `/acs:ship` names you in its `ship.yaml` per-path
`skill` mapping, and `/acs:code` dispatches to you when the ticket's recorded
`delivery_path` is `standard`. Nobody picks a path by hand — it is judged once
from `plan.md` (ADR-0095). If you believe the path is wrong for the work in
front of you, the remedy is never to behave like another path: the review's
**Path audit** dimension exists to say so, and `stop_reason: plan_superseded`
is how a run asks for a corrected plan.

## What to read, and when

Three references hold everything the four delivery paths share. Read all three
— they are not conditional branches, they are this run's protocol, split out so
that a path only carries what makes it different:

| Read | For |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md` | Start, Branch, Resume & reconcile, Plan input resolution, docs-only tickets, user interaction, context pressure, Finish and the completion report |
| `${CLAUDE_PLUGIN_ROOT}/skills/code/references/execute.md` | the execute phase: TDD order, the comment policy, Simplicity First, Surgical Changes, the commit |
| `${CLAUDE_PLUGIN_ROOT}/skills/code/references/verify.md` | the review's dimensions, the verdict rules, the coverage hard fail |

Everything below is what THIS path does differently. Where this file and a
reference disagree about executors, verifier shape or the iteration ceiling,
this file wins — that is the whole reason it exists.

## The machinery of this path

| | this path |
|---|---|
| Executors | parallel, per the file map |
| Verifier | one pass, all 16 dimensions |
| Iteration ceiling | **3** execute -> verify rounds |
| Plan approval | **enforced** |

### Executors

**Parallel executors, per the plan's file map.** Spawn one per disjoint file
group, in a single message so they run concurrently; any overlap — source,
tests, or docs — means those groups run sequentially instead.

### Verifier

**One `acs:code-verifier` spawn**, no lens constraint and no `-lens-` suffix,
writing `<partition>/phases/code/iter-<n>-verify.md` directly.

### Dimensions

Every dimension in `references/verify.md`, **Regression-risk (git-history)**
(dimension 14) included.

### Inputs

`test-cases.md` and, when the analysis found an API surface change,
`api-contract.md` are required verifier inputs. The contract-conformance
sub-check of the architecture dimension binds whenever `api-contract.md` exists.

### Plan approval

**Plan approval is enforced.** `<partition>/phases/code/plan-approval.json`
must record an eligible approval whose `plan_sha256` matches the current
`plan.md` bytes; the plan-conformance dimension is then ACTIVE and a changed
file tracing to no entry of the approved `## Executor tasks & file map` is a
blocking finding. A missing or stale approval is not yours to write: fail the
run with `stop_reason: plan_superseded`, which sends /acs:ship back to
`/acs:create-impl-plan`.

## The reflection loop

Run execute -> verify for at most **3** iterations. There is no plan
phase and no planner subagent: `/acs:create-impl-plan` authored the plan before
this skill started, and this run reads it (Plan input resolution, in
`references/protocol.md`).

Spawn subagents with the Agent tool: `acs:code-executor` and `acs:code-verifier` (fall back to the
un-namespaced name only if the runtime rejects the namespaced one). For each
role, apply `context.models.<role>.model`
/ `.effort` at spawn when not `"inherit"`; if the runtime rejects the model or
effort, FAIL the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

Messaging rules (schemas/acs-messages.xsd):

- Send each subagent one `<task skill="code" phase="execute|verify"
  ticket-id="<id>" iteration="n">` containing `<objective>`, `<inputs>` (file
  refs: the resolved `plan.md`, `test-cases.md` and `api-contract.md` when
  they exist, spec files, the ticket document, design.md when it applies, repo
  paths), and `<constraints>`. The subagent returns a `<result>` as its final
  content.
- Validate EVERY message you send and receive:

  ```bash
  echo "<xml>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
  ```

  On invalid: re-request once with the validation error; still invalid -> fail
  the run and record the error in the result document's `errors`.
- Persist every phase output to
  `<partition>/phases/code/iter-<n>-<phase>.xml` at the phase boundary,
  BEFORE starting the next phase.
- Decomposition is YOURS alone — subagents never spawn subagents. You MAY run
  several executors in parallel ONLY when their specs touch disjoint files
  (per the plan's file map); any overlap — source, tests, or docs — means
  sequential execution. The verifier runs after all executors finish and
  judges the combined changeset.

## The /acs:ship context boundary

`ship.yaml` gives this path `boundary: full_verify_stop`. Your whole reflection
cycle runs inside the ship coordinator's context, so when /acs:ship invoked you
it stops after you complete rather than carrying on to the tail of the pipeline.
That is a designed boundary, not a failure, and it is /acs:ship's to act on —
you simply finish normally and return your handoff.
