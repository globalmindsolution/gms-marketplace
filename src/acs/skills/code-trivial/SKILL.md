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
writing `steps/code/iter-<n>-verify.md` directly.

### Dimensions

All dimensions in `${CLAUDE_PLUGIN_ROOT}/skills/code/references/verify.md` EXCEPT **Regression-risk
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
plan-conformance dimension then reports N/A, exactly as `${CLAUDE_PLUGIN_ROOT}/skills/code/references/verify.md`
describes. Do not create one.

## The reflection loop

Run execute -> verify for at most **2** iterations. There is no plan
phase and no planner subagent: `/acs:create-impl-plan` authored the plan before
this skill started, and this run reads it (Plan input resolution, in
`${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md`).

Spawn the executors and the verifier as `${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md`'s
**Subagents and messaging** section describes — the agent names, the
model/effort resolution, the foreground-wait rule, the XML task and
result contract, and the phase-artifact persistence are identical on
every path.
