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
writing `steps/code/iter-<n>-verify.md` directly.

### Dimensions

Every dimension in `${CLAUDE_PLUGIN_ROOT}/skills/code/references/verify.md`, **Regression-risk (git-history)**
(dimension 14) included.

### Inputs

`test-cases.md` and, when the analysis found an API surface change,
`api-contract.md` are required verifier inputs. The contract-conformance
sub-check of the architecture dimension binds whenever `api-contract.md` exists.

### Plan approval

**Plan approval is enforced.** `steps/code/plan-approval.json`
must record an eligible approval whose `plan_sha256` matches the current
`plan.md` bytes; the plan-conformance dimension is then ACTIVE and a changed
file tracing to no entry of the approved `## Executor tasks & file map` is a
blocking finding. A missing or stale approval is not yours to write: fail the
run with `stop_reason: plan_superseded`, which sends /acs:ship back to
`/acs:create-impl-plan`.

## Plan approval — run it at Start, before the first executor

This path requires an approved plan, and this leg is where approval is
established: `/acs:create-impl-plan` runs before any delivery path exists, so
it cannot know whether approval is owed. Immediately after Start, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/plan-approval.py" --ticket <ticket-id>
```

This script is the ONLY writer of `steps/code/plan-approval.json`
— never a subagent's `Write` tool, and never your own. An LLM-asserted approval
is not an approval: eligibility is computed by `acs_lib.plan_approval_eligible`
from the plan artifact's own content plus `settings.test_coverage_percent`,
never from any agent's self-report. It hashes the approval mirror
(`steps/code/plan.md`), which is why `/acs:create-impl-plan`
publishes that copy from the same bytes as the plan; an explicit `--plan` must
resolve within `steps/code/` and the script refuses (clean stderr,
exit 2, no record written) any path whose realpath escapes it.

It is idempotent per digest: a second invocation over the same plan bytes
re-asserts the existing verdict, and a revised plan writes a fresh record. So a
resumed run simply runs it again.

**An ineligible plan does not block this release.** The script exits 0 and
prints the failing checks; record `states.plan_approved: false` and continue.
The plan-conformance review dimension reads `plan-approval.json` itself and
computes its own activation, so an ineligible plan means that dimension reports
N/A — not that the run proceeds unreviewed.

## The reflection loop

Run execute -> verify for at most **3** iterations. There is no plan
phase and no planner subagent: `/acs:create-impl-plan` authored the plan before
this skill started, and this run reads it (Plan input resolution, in
`${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md`).

Spawn the executors and the verifier as `${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md`'s
**Subagents and messaging** section describes — the agent names, the
model/effort resolution, the foreground-wait rule, the XML task and
result contract, and the phase-artifact persistence are identical on
every path.

## After this path completes, /acs:ship stops

`ship.yaml` gives this path `boundary: full_verify_stop`. The stop is
/acs:ship's, not yours — this section is here so a reader of this leg knows
what happens after it, not because the leg does anything about it. Your whole reflection
cycle runs inside the ship coordinator's context, so when /acs:ship invoked you
it stops after you complete rather than carrying on to the tail of the pipeline.
That is a designed boundary, not a failure, and it is /acs:ship's to act on —
you simply finish normally and return your handoff.
