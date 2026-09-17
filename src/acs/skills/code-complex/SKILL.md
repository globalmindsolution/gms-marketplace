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
   the zero-findings rule below — the merge pass changes WHICH findings
   count, never the pass/fail rule itself. **`iter-<n>-verdict.json` governs
   `verifier_passed`**; the report explains it. The in-loop escalation
   check's trigger (a) (see
   `${CLAUDE_PLUGIN_ROOT}/skills/code/references/lane-changes.md`) reads this
   FINAL merged findings list — the merge write always happens before the
   next iteration's trigger-(a) evaluation.

### Dimensions

Every dimension in `references/verify.md`, **Regression-risk (git-history)**
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

`ship.yaml` gives this path `boundary: full_verify_stop`. Four lens spawns per
iteration, up to three iterations, all inside the ship coordinator's context: this
is the path that boundary was written for. /acs:ship stops after you complete and
runs the pipeline's tail in a fresh session. You simply finish normally.
