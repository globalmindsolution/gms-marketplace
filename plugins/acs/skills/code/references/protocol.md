# /acs:code — the protocol every delivery path shares

*Read by whichever `code` leg is running. Path:*
*`${CLAUDE_PLUGIN_ROOT}/skills/code/references/protocol.md`.*

Four legs implement the `code` step — `code-trivial`, `code-small`,
`code-standard`, `code-complex` — and everything below is identical in all
four. What differs is how many implementers run and whether an integration
implementer follows them; that lives in each leg's own SKILL.md, which is the
only file that needs reading to know what a path costs.

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
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step code --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround. The pre-hook refuses only what running now would
damage: the run must resolve to a live, unlocked partition, an epic ticket is
never implemented, and when a plan records a deep path its approval must be present
and current. It never refuses because an upstream artifact is missing and
requires no predecessor step to have completed — the order lives in
`workflows/ship.yaml`, not in this gate. A run with no plan on disk is
`/acs:code`'s own business: it derives an implicit plan for the cheap paths
from the subject (see `/acs:code`'s **No plan at all**).

Parse the printed context JSON. Fields you will use:

- `run_id`, `subject` — what this run is about. A subject is a **ticket, a
  prompt or a document** (§3.11), or a mix of them (`subject.sources`).
- `requirements` — `{path, sources, acceptance_criteria, features, feature,
  needs_design}`. **Requirements: `context.requirements` / `acs.py requirements
  show` — a ticket id, documents and a prompt are only where they came from;
  never read ticket.json for acceptance criteria.** The implementation must
  satisfy every criterion in `requirements.path` (the run's `requirements.md`).
  `ticket` is present only when a ticket is one of the sources.
- `partition` — absolute path of the run directory. Read `plan.md` (see Plan
  input resolution), `test-cases.md` and `api-contract.md` when they exist —
  `acs.py artifacts show` reports each (`<development_dir>/<feature>/<id>/` for
  `plan.md` and `test-cases.md`, `<architecture_dir>/lld/<feature>/<id>/` for
  `api-contract.md` and `design.md`, a legacy `docs/tickets/<ID>/` file only
  when the new folder has none) — and the analyses it reports: the run's
  analysis and the feature's living analysis (`feature_analysis`,
  `<prd_dir>/features/<feature>/analysis/`), for the impact map and risks the
  change was planned against. Each is a folder (ADR-0133): its `README.md`
  (`artifacts["analysis.md"]`) first, then only the context files the plan's
  file map touches (`analysis_files`); a legacy single `analysis.md` whole.
  Step artifacts go in `steps/code/`.
- `iteration` — the review loop's current iteration. The context carries
  **no** `verdict` key: on iteration `n` ≥ 2, read the verdict the previous
  review wrote from disk — `steps/review-code/verdict.json` in `partition`
  (the step root, `acs_lib.artifact_path(partition, "verdict")`), whose
  per-iteration copy is `steps/review-code/iter-<n-1>/verdict.json`
  (`acs_lib.verdict_path(partition, "review-code", n - 1)`); `acs.py verdict
  show --iteration <n-1>` prints that copy validated. Then see
  **On iteration 2+** in your leg's SKILL.md.
- `design` — `{required, dir, source}` when a design document applies.
- `settings` — you need `tests.e2e` when set. The repo's standards set and `tests.coverage` are
  the **reviewer's** inputs, not yours.
- `agents` — the agent name to spawn per role; the implementer's model and
  effort come from `settings.models.code.implementer` (inheriting when unset).
- `reconcile`, `handoff_summary`, `prior_status` — see Resume & reconcile.

---

## Subagents and messaging

Every leg spawns one kind of agent — the implementer,
`subagent_type: "acs:code-implementer"`, one per file-map partition — and
obeys the same messaging rules. There is no planner and no verifier: the plan
is `/acs:create-impl-plan`'s and the review is `/acs:review-code`'s. What a leg
decides is HOW MANY implementers to spawn and whether an integration
implementer follows.

Spawn subagents with the Agent tool: `acs:code-implementer` (fall back to the
un-namespaced `code-implementer` only if the runtime rejects the namespaced
one). The implementer is a `write`-kind role. Spawn it under the name in
`context.agents.implementer` — the plugin's `acs:code-implementer`, or the
generated `acs-code-implementer` copy `acs step start` wrote where
`settings.models` sets a model or effort for it. Model and effort travel with
that agent, so pass none of your own. If the runtime rejects the agent, FAIL the
run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the implementer's result is your
next input and nothing else can usefully happen while it runs. If the runtime
moves the agent to the background anyway, wait for its completion notification
— never poll with `sleep` loops, which wait a fixed interval whatever the agent
did.

Messaging rules (the SubagentStop hook checks them):

- Send each implementer one task message, `<task skill="code"
  phase="implementer" …>`, carrying `objective`, `inputs` (file refs: the
  resolved `plan.md`, `test-cases.md` and `api-contract.md` when they exist,
  `requirements.md`, the analysis and the feature's living analysis when they
  exist, `design.md` when it applies, repo paths) and
  `constraints`. The implementer returns a `<result skill="code"
  phase="implementer" …>` document as its final content. When several
  implementers run at once, each task and its result carry the slice id,
  `slice="<k>"` (the plan task number the partition is), so the SubagentStop
  snapshots of parallel slices never collide; a single implementer omits it.
- Messages are **JSON**, validated in the hook. There is no XSD and no
  second validator in another language: a malformed message is refused with
  the reason, and you re-send it once before failing the run.
- Each implementer writes its report to `steps/code/iter-<n>/implementer.json`
  (`iter-<n>/implementer-<k>.json` when several run in parallel), and the
  SubagentStop hook snapshots its returned message beside it. Persist every
  other phase output under `steps/code/iter-<n>/` at the phase boundary,
  BEFORE starting the next phase.
- Decomposition is YOURS alone — subagents never spawn subagents. Parallel
  implementers are allowed ONLY when their partitions touch disjoint files (per
  the plan's file map); any overlap — source, tests, or docs — means sequential
  execution. When they are disjoint, parallel is the default from iteration 1:
  every implementer of a wave is spawned in ONE message, at most
  `settings.parallel.max_agents` (default 4) per wave, and you wait for all of them before the next
  phase (`execute.md`, **Parallel implementers**).

---

### Epics are never implemented

An epic ticket (a ticket-only check: a prompt or document run has no type) is refused by the `code` gate before this skill ever starts —
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

## Working tree — no branch, no commits

All work happens in the working tree, on whatever is checked out. This step
never creates, switches or names a branch, and never stages, commits or pushes
(ADR-0127): every file an implementer writes stays an uncommitted change,
listed in its report's `files_changed`, and the run records the union in the
result's `states.files`. `/acs:create-pr` is the only skill that branches and
commits — it reads those reports to split the change into a tests commit and a
code commit per partition. Never commit to "save" work: the working tree is
where the work lives until then.

---

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Read `steps/code/state.json` (`invocations[-1]` and `states`) and the
   artifacts under `steps/code/iter-*/` to see what was recorded implemented
   and where the prior invocation stopped.
2. See what the prior invocation left in the working tree:
   `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" changes diff --name-only`
   — uncommitted by design (see Working tree); never stash, reset or commit it.
3. Re-run **the tests your change touches** — once. Trust nothing that fails: a
   task whose tests fail or whose files are missing is NOT done, whatever the
   state file says. The full suite is the reviewer's gate, not yours.
4. Continue from the first unfinished task of the recorded iteration. When
   that iteration ran sliced, re-run only the slices whose report
   (`iter-<n>/implementer-<k>.json`) is missing, or whose targeted tests step 3
   found red — each under its original `k`, still in one message. A slice with
   its report on disk and green tests is done and is never re-spawned. Then the
   integration slice, when your leg owes one and
   `iter-<n>/implementer-integration.json` is missing.

If `context.handoff_summary` exists, read it plus
`steps/code/handoff-context.md` (if present), do a light reconcile (trust the
summary, but cheaply verify by running the tests it says pass), and continue
from where it points.

### Plan input resolution

The plan is an INPUT here, never an output: `/acs:create-impl-plan` wrote it
and this skill reads it. It is at `steps/create-impl-plan/plan.md` when
`/acs:create-impl-plan` ran for this run (`acs.py plan path` names the one it
read). On a standalone run with no plan, `/acs:code` derived an implicit plan
from the requirements for the cheap paths and recorded it at `steps/code/plan.md`;
that file is the plan for this run. There is no approval mirror: one plan, one
path, and `plan-approval.json` hashes that same file.

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

When the run's ticket carries the user-confirmed `docs_only` flag, the TDD steps
relax — the delivery guarantees do not: implementers skip
write-failing-tests-first and new-test generation, and the existing tests are
still run once and must be green (a docs-only change that breaks the build is a
finding the review will raise). If any implementer finds itself touching
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
work that would be lost. Leave the green work in the working tree (never
commit it to save it), flush
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
       "tasks_implemented": ["01-data-model", "02-import-endpoint"],
       "tests": {"passed": 84, "failed": 0},
       "docs_updated": ["README.md", "docs/api/import.md"],
       "files": ["src/import/api.py", "tests/test_import_api.py", "README.md",
                 "docs/api/import.md"]
     },
     "findings": [],
     "errors": []
   }
   ```

   `files` is the union of every implementer report's `files_changed` this
   invocation — the repo-relative paths left uncommitted for `/acs:create-pr`.

   On iteration 2+ it also carries `since_sha` and a `resolutions` entry for
   **every** confirmed finding of the verdict — see **On iteration 2+** in your
   leg's SKILL.md.

   **Some keys are DERIVED.** `tests`, `pr` and `review.*` are computed by the
   post-hook from the artifacts on disk. Write your best value anyway (the
   document is a contract with humans too), but what lands is the computed one,
   and a disagreement is recorded and printed. `verifier_passed` is **not
   yours at all**: it is derived from `/acs:review-code`'s verdict, and you
   cannot open the `/acs:create-pr` gate by writing it.

   On failure keep whatever is true: the files written, the tasks that ARE implemented
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
   index, and releases the run lock. A step that ends at
   `step finish` leaves `verifier_passed` underived — which shuts
   `/acs:create-pr`'s brake permanently — and the lock held.

3. Report a compact summary to the user: what was implemented, the
   uncommitted files it left in the working tree, the targeted tests' result,
   docs updated, and the next step
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
- **Results**: what was implemented; targeted tests passed/failed; docs updated
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <uncommitted files written (repo-relative), run files>
- **Metrics**: iteration <n>/<cap> · <wall time>
- **Next**: `/acs:review-code` on success (the files stay uncommitted until `/acs:create-pr`); on `needs_input`, answer the questions and re-run; on a plan failure, `/acs:create-impl-plan`
```

Any assumption recorded during the run surfaces on the **Findings** line
alongside open findings and clarifications, or `none` when there are none.
