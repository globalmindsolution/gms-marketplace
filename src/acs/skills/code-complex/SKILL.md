---
name: code-complex
description: Implement a ticket's plan on the COMPLEX delivery path — parallel executors, a four-lens verifier whose findings are merged and adversarially re-scrutinised, a three-iteration ceiling, with plan approval enforced. Dispatched by /acs:ship (or /acs:code) after the plan is judged complex; never chosen by hand.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of the **complex** delivery path of /acs:code — the deepest path.
Your job: implement one ticket's existing plan in the consumer repo, tests
first, committed on the ticket branch, and pass the built-in changeset review.

You are a leg, not a command. `/acs:ship` names you in its `ship.yaml` per-path
`skill` mapping, and `/acs:code` dispatches to you when the ticket's recorded
`delivery_path` is `complex`. Nobody picks a path by hand — it is judged once
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
| Verifier | **four lenses**, merged |
| Iteration ceiling | **3** execute -> verify rounds |
| Plan approval | **enforced** |

### Executors

**Parallel executors, per the plan's file map.** Spawn one per disjoint file
group, in a single message so they run concurrently; any overlap — source,
tests, or docs — means those groups run sequentially instead.

### Verifier

**The multi-lens spawn.** After all executors finish,
the coordinator spawns 4 parallel `acs:code-verifier` subagents via the
Agent tool — the same agent file, four times, reusing the "several
executors in parallel... per the plan's file map" spawn mechanism already
used for executors above — each `<task phase="verify">` carrying one
additional `<constraint name="verify_lens">A|B|C|D</constraint>` (lens
table: `code-verifier.md`'s Multi-lens review section). Each lens spawn
writes its own `<partition>/phases/code/iter-<n>-verify-lens-<A|B|C|D>.md`
artifact (never the shared `iter-<n>-verify.md` name) and returns its
`<result>` with `lens="<A|B|C|D>"` set to the lens it was given — that
attribute is how you tell the four results apart and how the SubagentStop
hook finds each lens's verdict file; a lens result without it fails
validation of its verdict. After all 4 lenses
return, the coordinator itself performs the merge pass — never a subagent:

1. Collect every `<finding>` across the 4 lens results.
2. A finding raised, in substance, by **2 or more** lenses is corroborated
   — kept blocking without further check.
3. A finding raised by exactly **one** lens is adversarially re-scrutinized
   by the coordinator itself: re-read the finding's cited evidence
   directly. If the evidence supports the claim, keep it blocking; if the
   coordinator cannot independently confirm it, downgrade it to
   `severity="info"` with the downgrade rationale recorded — never silently
   dropped (the cross-lens application of "if it is not worth blocking, it
   is not a finding — note it in the report only").
4. **The downgrade is recorded in the LENS VERDICT, before the merge.** A
   finding the coordinator re-scrutinized and could not confirm is rewritten
   to `severity="info"` in that lens's own `iter-<n>-verdict-<lens>.json`,
   which the coordinator may edit for exactly this purpose and no other.
   It must NOT be downgraded afterwards in the merged document:
   `acs.py verdict merge` is a pure union with no downgrade step, so a
   downgrade applied after it would make the report say "pass" while the
   verdict says `passed: false` — and `verifier_passed` is read from the
   VERDICT (MAR-523), not from the report. Order matters: re-scrutinize,
   amend the lens verdict, then merge.
5. The coordinator writes the single merged
   `<partition>/phases/code/iter-<n>-verify.md` itself: one section per
   corroborated/confirmed finding (blocking), one per downgraded finding
   (info-level, with rationale), and a short per-lens evidence summary.
   `acs.py verdict merge` writes the merged verdict from the four lens
   verdicts; it refuses a subset of lenses, and refuses to replace a verdict
   that carries blocking findings with a passing one.
6. Zero surviving blocking findings after the merge = pass, identical to
   the zero-findings rule in `${CLAUDE_PLUGIN_ROOT}/skills/code/references/verify.md` — the merge pass changes
   WHICH findings count, never the pass/fail rule itself.
   **`iter-<n>-verdict.json` governs `verifier_passed`**; the report explains
   it. The merged list is also what the next iteration's executors are given
   as `<context>`, so the merge write always happens before the next iteration
   starts.

### Dimensions

Every dimension in `${CLAUDE_PLUGIN_ROOT}/skills/code/references/verify.md`, **Regression-risk (git-history)**
(dimension 14) included — it is lens D's.

### Inputs

`test-cases.md` and, when the analysis found an API surface change,
`api-contract.md` are required verifier inputs, as is `design.md` (own or
parent) whenever the ticket has one.

### Plan approval

**Plan approval is enforced**, exactly as on `standard`:
`<partition>/phases/code/plan-approval.json` must record an eligible approval
whose `plan_sha256` matches the current `plan.md` bytes, the plan-conformance
dimension is ACTIVE, and a missing or stale approval fails the run with
`stop_reason: plan_superseded` rather than being written here.

## Plan approval — run it at Start, before the first executor

This path requires an approved plan, and this leg is where approval is
established: `/acs:create-impl-plan` runs before any delivery path exists, so
it cannot know whether approval is owed. Immediately after Start, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/plan-approval.py" --ticket <ticket-id>
```

This script is the ONLY writer of `<partition>/phases/code/plan-approval.json`
— never a subagent's `Write` tool, and never your own. An LLM-asserted approval
is not an approval: eligibility is computed by `acs_lib.plan_approval_eligible`
from the plan artifact's own content plus `settings.test_coverage_percent`,
never from any agent's self-report. It hashes the approval mirror
(`<partition>/phases/code/plan.md`), which is why `/acs:create-impl-plan`
publishes that copy from the same bytes as the plan; an explicit `--plan` must
resolve within `<partition>/phases/code/` and the script refuses (clean stderr,
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
what happens after it, not because the leg does anything about it. Four lens spawns per
iteration, up to three iterations, all inside the ship coordinator's context: this
is the path that boundary was written for. /acs:ship stops after you complete and
runs the pipeline's tail in a fresh session. You simply finish normally.
