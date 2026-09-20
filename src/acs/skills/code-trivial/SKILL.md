---
name: code-trivial
description: Implement a subject's plan on the TRIVIAL delivery path — one executor, the plan's own test strategy as the test contract, no plan approval. Dispatched by /acs:code after the plan records delivery_path trivial; never chosen by hand.
argument-hint: "[ticket-id | prompt | document]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of the **trivial** delivery path of /acs:code — the cheapest path.
Your job: implement this run's existing plan in the consumer repo, tests first,
committed on the run's branch.

You are a leg, not a command. `/acs:code` dispatches to you when the plan's
`## Contract` block records `delivery_path: trivial`. Nobody picks a path by
hand — it is judged once, by `/acs:create-impl-plan`, from the work itself
(ADR-0095). If you believe the path is wrong for the work in front of you, the
remedy is never to behave like another path: say so, and
`stop_reason: needs_input` is how a run asks for a corrected plan.

## What to read, and when

Two references hold everything the four delivery paths share. Read both — they
are not conditional branches, they are this run's protocol, split out so that a
path only carries what makes it different:

| Read | For |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md` | Start, Branch, Resume & reconcile, Plan input resolution, docs-only subjects, user interaction, context pressure, Finish and the completion report |
| `${CLAUDE_PLUGIN_ROOT}/skills/code/references/execute.md` | the execute phase: TDD order, the comment policy, Simplicity First, Surgical Changes, the commit |

Everything below is what THIS path does differently. Where this file and a
reference disagree about executors, this file wins — that is the whole reason
it exists.

## The machinery of this path

| | this path |
|---|---|
| Executors | one, always |
| Test contract | the plan's **Test strategy** section |
| Plan approval | not required |

### Executors

**Exactly one executor. Never parallel.** A plan judged `trivial` is one
coherent change; splitting it across executors would cost two subagent spawns
and a merge to save nothing. Give that executor the whole file map.

### Inputs

`create-test-docs` records `no_cases_owed` on this path, so there is no
`test-cases.md`. The plan's own **Test strategy** section is the test contract.

### Plan approval

**Plan approval is not required.** `plan-approval.json` may be absent, and
`/acs:code`'s pre-hook does not ask for one on this path. Do not create one.

## You do not review your own work

**This path has no verifier.** The changeset review is `/acs:review-code`, the
next step in `ship.yaml`, and every delivery path gets the same one: five
lenses, one fresh-context adjudicator per finding, and a final gate running
build, lint, the full unit suite and coverage. The review scales itself from
the changeset in front of it; you neither size it nor spawn it.

Two things left with the verifier, and both were review properties rather than
implementation properties:

- **verifier shape** — one pass or four lenses — is now the reviewer's own
  call, measured from the diff
- **the iteration ceiling** is now `ship.yaml`'s `loop.max_iterations`, the
  same cap on every path

Run the tests your change touches, not the full suite: the gate runs it once,
last, on the iteration that survives review. That discipline is safe precisely
because the guarantee is unconditional and terminal rather than buried inside
an iteration that may be discarded.

## On iteration 2+

`acs step start` tells you the iteration and whether a verdict exists. On
iteration 2 and later, read `steps/review-code/verdict.json` and nothing else
from the review — not the lens reports, not the adjudication transcripts.

Answer **every** confirmed finding by id in your `result.json`, `fixed` or
`disputed`; there is no third option:

```jsonc
{ "iteration": 2, "since_sha": "<the verdict's reviewed_sha>",
  "resolutions": [
    { "id": "F-1-3", "status": "fixed", "commits": ["b7a2…"],
      "tests": ["tests/auth/test_session.py::test_refresh_keeps_tenant"] },
    { "id": "F-1-5", "status": "disputed",
      "reason": "the lookback flagged a revert of a different function with the same name; evidence: …" }
  ] }
```

Work to the finding's `resolved_when`, not to its wording: that field is the
refutation criterion the adjudicator could not satisfy, restated as what your
fix must make true. TDD still applies inside the loop — a behavioural finding
gets its failing test first.

`disputed` is not a way out. The next review's adjudicator receives the dispute
as additional evidence and rules again, and a finding disputed then confirmed a
second time stops the run with `stop_reason: needs_input` so a human breaks the
tie.

