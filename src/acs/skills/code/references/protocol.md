# /acs:code — the protocol every delivery path shares

*Read by whichever `code` leg is running. Path:*
*`${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md`.*

Four legs implement the `code` step — `code-trivial`, `code-small`,
`code-standard`, `code-complex` — and everything below is identical in all
four. What differs is how many executors run and whether an integration
executor follows them; that lives in each leg's own SKILL.md, which is the only
file that needs reading to know what a path costs.

**The legs share `code`'s identity on disk.** Every one of them starts with
`acs step start --step code`, so the run, `steps/code/`, the step's
`state.json`, the `code` ledger key and the post-hook are the same whichever
leg ran. The leg name appears in exactly one place: the Skill invocation. A
resumed run therefore reads artifacts a different session wrote without caring
which leg wrote them.

**You have no verifier.** The review is `/acs:review-code`, the next step in
`ship.yaml`. Nothing below spawns, sizes or waits on a reviewer.

---

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step code
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround. The pre-hook has verified this step's inputs: the run
resolves to a live, unlocked partition, a plan exists, and on the deep paths
the plan's approval is present and current. The gate is the same on every
delivery path and requires no predecessor step to have completed — the order
lives in `workflows/ship.yaml`, not in this gate.

Parse the printed context JSON. Fields you will use:

- `run_id`, `subject` — what this run is about. A subject is a **ticket, a
  prompt or a document** (§3.11); `subject.kind` says which. The implementation
  must satisfy it.
- `partition` — absolute path of the run directory. Read `plan.md` (see Plan
  input resolution), `test-cases.md` and `api-contract.md` when they exist.
  Step artifacts go in `steps/code/`.
- `iteration` — the review loop's current iteration, and `verdict` when a
  previous review left one. On iteration 2+ see **On iteration 2+** in your
  leg's SKILL.md.
- `design` — `{required, dir, source}` when a design document applies.
- `settings` — you need `formats.branch_name`, `formats.commit_message`, and
  `e2e` when set. `standards_path` and `test_coverage_percent` are the
  **reviewer's** inputs, not yours.
- `models` — per-role `{model, effort}` for the executor.
- `reconcile`, `handoff_summary`, `prior_run_status` — see Resume & reconcile.

---

## Subagents and messaging

Every leg spawns one agent — `acs:code-executor` — and obeys the same
messaging rules. What a leg decides is HOW MANY to spawn and whether an
integration executor follows.

Spawn subagents with the Agent tool: `acs:code-executor` (fall back to the
un-namespaced name only if the runtime rejects the namespaced one). Apply
`context.models.executor.model` / `.effort` at spawn when not `"inherit"`; if
the runtime rejects the model or effort, FAIL the run with that exact error —
no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the executor's result is your
next input and nothing else can usefully happen while it runs. If the runtime
moves the agent to the background anyway, wait for its completion notification
— never poll with `sleep` loops, which wait a fixed interval whatever the agent
did.

Messaging rules (the SubagentStop hook checks them):

- Send each subagent one task message carrying `objective`, `inputs` (file
  refs: the resolved `plan.md`, `test-cases.md` and `api-contract.md` when they
  exist, the subject document, `design.md` when it applies, repo paths) and
  `constraints`. The subagent returns a result document as its final content.
- Messages are **JSON**, validated in the hook. There is no XSD and no
  second validator in another language: a malformed message is refused with
  the reason, and you re-send it once before failing the run.
- Persist every phase output under `steps/code/iter-<n>/` at the phase
  boundary, BEFORE starting the next phase.
- Decomposition is YOURS alone — subagents never spawn subagents. Parallel
  executors are allowed ONLY when their partitions touch disjoint files (per
  the plan's file map); any overlap — source, tests, or docs — means sequential
  execution.

---

### Epics are never implemented

An epic subject is refused by the `code` gate before this skill ever starts —
the epic brake runs for every implementation step, so an epic is turned away
at `analyze-requirements` rather than three steps later with a plan on disk.
Every ticket that reaches this
step therefore has `ticket.type != "epic"`.

That invariant is true of a gate that fired. If `ticket.type == "epic"`
nonetheless reaches this step — a bypassed or best-effort pre-gate on some
runtimes — STOP immediately and surface the same breakdown message the gate
would have raised: design the epic with `/acs:create-design <id>` if it has
none, break it down into child tickets with `/acs:create-ticket <id>` (epic
fan-out), then run `/acs:code` on a child. **Never implement an epic under any
circumstance**, regardless of what the pre-gate did or did not enforce.

This is defence in depth, and it is a rule of every delivery path: a leg that
received an epic refuses it exactly as the gate would, rather than judging it
onto a path and implementing it.

---

## Branch — FIRST, before any code

All work happens on the run's branch. Render `settings.formats.branch_name`
(default `"{type}/{ticket_id}-{slug}"`) with:

- `{ticket_id}` — the run's ticket id when the subject is a ticket, the run id
  otherwise;
- `{type}` — the subject's type (`epic|story|task`), `task` when it has none;
- `{slug}` — the slugified subject title: lowercase, every non-alphanumeric run
  becomes `-`, trimmed, max 40 chars (`acs slug` renders exactly this);
- `{external_key}` — the tracker's key when set, else empty.

Then create or reuse it:

```bash
git rev-parse --verify --quiet "<branch>" && git checkout "<branch>" || git checkout -b "<branch>"
```

On resume the branch usually already exists — reuse it, never recreate or reset
it. Every commit message follows `settings.formats.commit_message` (default
`"{ticket_id} {summary}"`). Commit work on this branch as the plan's tasks
land; do NOT push — `/acs:create-pr` owns the push and the PR.

---

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Read `steps/code/state.json` (`invocations[-1]` and `states`) and the
   artifacts under `steps/code/iter-*/` to see what was recorded implemented
   and where the prior invocation stopped.
2. Check out the recorded `states.branch` (it should exist — see Branch).
3. Re-run **the tests your change touches** — once. Trust nothing that fails: a
   task whose tests fail or whose files are missing is NOT done, whatever the
   state file says. The full suite is the reviewer's gate, not yours.
4. Continue from the first unfinished task of the recorded iteration.

If `context.handoff_summary` exists, read it plus
`steps/code/handoff-context.md` (if present), do a light reconcile (trust the
summary, but cheaply verify by running the tests it says pass), and continue
from where it points.

### Plan input resolution

The plan is an INPUT here, never an output: `/acs:create-impl-plan` wrote it
and this skill reads it. It is at `steps/create-impl-plan/plan.md`, and the
pre-hook resolved it before this skill started. There is no approval mirror:
one plan, one path, and `plan-approval.json` hashes that same file.

Its `## Contract` block is the machine-readable minimum — `delivery_path`,
what the run `owes`, and the `### Executor tasks & file map` heading your
partitions come from. Read it first; it is what dispatched you here.

**Never author or revise it.** If the plan is missing on resume, or execution
proves it wrong — a task it does not cover, a file map that cannot work, an
approach the codebase refuses — do NOT re-plan here: stop at the iteration
boundary, write `result.json` with `status: "failed"` and
`stop_reason: needs_input` naming what the plan got wrong, run the Finish
steps, and point at `/acs:create-impl-plan`.

---

## Docs-only subjects

When the subject carries the user-confirmed `docs_only` flag, the TDD steps
relax — the delivery guarantees do not: executors skip
write-failing-tests-first and new-test generation, and the existing tests are
still run once and must be green (a docs-only change that breaks the build is a
finding the review will raise). If any executor finds itself touching
executable code or tests, STOP — the flag is wrong; surface it to the user and
have the subject corrected before continuing.

---

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` and reuse any
recorded answer — re-asking an answered question is a defect. When ≥2
clarifications are open, present them in ONE grouped interaction (a single
AskUserQuestion containing all open questions as a numbered list), not serial
round-trips. Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer outside the existing
`--source assumption --rationale "..."` rule.

Record every Q&A — obtained interactively or relayed in a `/acs:ship` brief —
with `clarify.py add --skill code --question "..." --answer "..."` BEFORE
acting on it, and pass the relevant `C-n` entries to subagents in `context`. If
the user is unavailable or says "you decide": record the decision with
`--source assumption --rationale "..."` — assumptions surface in the completion
report's Findings and in the PR body until a user confirms. Before a
`needs_input` stop, record the outgoing questions as `open` (`clarify.py add`
without `--answer`).

When the plan is genuinely ambiguous — it contradicts the design, leaves
behaviour undefined, or admits several implementations with different
user-visible outcomes — ask before executing. Do not guess on decisions that
change behaviour.

**The plan is not up for renegotiation here.** The oversize signal, the split
answer and any revision belong to `/acs:create-impl-plan`. If an ambiguity's
honest resolution is that the plan is wrong, end the step `failed` with
`stop_reason: needs_input` rather than implementing around it.

---

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Commit any uncommitted green work on the branch, flush
in-flight state plus soft context (user answers, decisions, partial findings,
what is green, gotchas) to `steps/code/handoff-context.md`, then finish the
step `interrupted` with `stop_reason: context_pressure`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-code.py" \
  --status interrupted --stop-reason context_pressure
```

Tell the user the command it prints, and stop. `interrupted` is the one
resumable state: a later session re-runs the step and reconciles.

---

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/code/result.json`:

   ```json
   {
     "status": "completed",
     "outcome": "implemented",
     "summary": "bulk import behind a feature flag, 3 partitions, 84 tests green",
     "iteration": 1,
     "states": {
       "branch": "task/SHOP-123-bulk-import",
       "tasks_implemented": ["01-data-model", "02-import-endpoint"],
       "tests": {"passed": 84, "failed": 0},
       "docs_updated": ["README.md", "docs/api/import.md"]
     },
     "findings": [],
     "errors": []
   }
   ```

   On iteration 2+ it also carries `since_sha` and a `resolutions` entry for
   **every** confirmed finding of the verdict — see **On iteration 2+** in your
   leg's SKILL.md.

   **Some keys are DERIVED.** `tests`, `pr` and `review.*` are computed by the
   post-hook from the artifacts on disk. Write your best value anyway (the
   document is a contract with humans too), but what lands is the computed one,
   and a disagreement is recorded and printed. `verifier_passed` is **not
   yours at all**: it is derived from `/acs:review-code`'s verdict, and you
   cannot open the `/acs:create-pr` gate by writing it.

   On failure keep whatever is true: the branch, the tasks that ARE implemented
   and green, docs actually updated, open findings in `findings`, and the
   reason in `summary`.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-code.py" \
     --result-file "<the result.json you just wrote>"
   ```

   The status, outcome and summary are read from `result.json` — a step's
   transition is read from its result document, not asserted on the command
   line. If it exits non-zero, surface its stderr verbatim: the next step's
   gate stays closed until it succeeds.

   The POST-HOOK, not `acs step finish`. The two are not alternatives:
   `step finish` closes the run's view of the step and stops there, while the
   post-hook does that AND derives the states from the artifacts, writes the
   index and the metrics, and releases the run lock. A step that ends at
   `step finish` leaves `verifier_passed` underived — which shuts
   `/acs:create-pr`'s brake permanently — and the lock held.

3. Report a compact summary to the user: branch, what was implemented, the
   targeted tests' result, docs updated, and the next step
   (`/acs:review-code` on success, `/acs:create-impl-plan` after a plan
   failure).

---

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed or
interrupted — ends your final message with the standard block
(`${CLAUDE_PLUGIN_ROOT}/docs/INTERNALS.md`, "Completion report"), rendered only
AFTER the post-hook succeeded. Same labels, same order, `none` where empty:

```markdown

## /acs:code · <run-id> · <status>

- **Subject**: <id or title> (<kind>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: branch; what was implemented; targeted tests passed/failed; docs updated
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <run files, repo paths, branch>
- **Metrics**: iteration <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:review-code` on success; on `needs_input`, answer the questions and re-run; on a plan failure, `/acs:create-impl-plan`
```

Any assumption recorded during the run surfaces on the **Findings** line
alongside open findings and clarifications, or `none` when there are none.
