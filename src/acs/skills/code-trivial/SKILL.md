---
name: code-trivial
description: Implement a ticket's plan on the TRIVIAL delivery path — one executor, one verifier pass, a two-iteration ceiling. Dispatched by /acs:ship (or /acs:code) after the plan is judged trivial; never chosen by hand.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of the **trivial** delivery path of /acs:code — the cheapest path.
Your job: implement one ticket's existing plan in the consumer repo, tests
first, committed on the ticket branch, and pass the built-in changeset review.

You are a leg, not a command. `/acs:ship` names you in its `ship.yaml` per-path
`skill` mapping, and `/acs:code` dispatches to you when the ticket's recorded
`delivery_path` is `trivial`. Nobody picks a path by hand — it is judged once
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
| Executors | one, always |
| Verifier | one pass |
| Iteration ceiling | **2** execute -> verify rounds |
| Plan approval | not required |

### Executors

**Exactly one executor. Never parallel.** A plan judged `trivial` is
one coherent change; splitting it across executors would cost two subagent
spawns and a merge to save nothing. Give that executor the whole file map.

### Verifier

**One `acs:code-verifier` spawn**, no lens constraint and no `-lens-` suffix,
writing `<partition>/phases/code/iter-<n>-verify.md` directly.

### Dimensions

All dimensions in `references/verify.md` EXCEPT **Regression-risk
(git-history)** (dimension 14), which is scoped to the two deep paths. Every
other dimension applies in full, the coverage gate included — a cheap path is a
path that spends less looking, never one that accepts less.

### Inputs

`create-test-docs` is SKIPPED on this path (`ship.yaml`), so there is no
`test-cases.md`. The plan's own **Test strategy** section is the test
contract, and the verifier judges acceptance-criteria coverage against the
ticket directly.

### Plan approval

**Plan approval is not required.** `plan-approval.json` may be absent; the
plan-conformance dimension then reports N/A, exactly as `references/verify.md`
describes. Do not create one.

## The reflection loop

Run execute -> verify for at most **2** iterations. There is no plan
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

