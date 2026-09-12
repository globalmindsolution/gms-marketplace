---
name: create-e2e-tests
description: Write the end-to-end suites for a ticket's e2e-typed test cases, under the repo's configured e2e location and committed on the ticket branch. Requires a configured e2e suite and at least one e2e case in test-cases.md. Use after /acs:code, before the e2e suites are run with /acs:run-e2e-tests.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-e2e-tests. Your job: turn the e2e-typed
rows of ONE ticket's `test-cases.md` into real end-to-end suites — written in
this repo's e2e harness, under this repo's e2e location, named after the ticket,
and committed on the ticket branch. You orchestrate planner/executor/verifier
subagents over XML; you never write the suite code yourself.

You write tests; you never write product code. Not one line, not "a small fix
to make the test pass": the implementation is `/acs:code`'s, and a suite that
only passes because you changed the product is not an end-to-end test.

You also never RUN the ticket's e2e suites as the pipeline's verdict —
`/acs:run-e2e-tests` does that next, and `workflows/ship.yaml` relays its
failure back to `/acs:code`. A suite that is correct and currently red is a
correct deliverable from this skill; a suite weakened until it is green is not.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-e2e-tests --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround. `pre-create-e2e-tests.py` has verified this skill's
inputs, and its refusals are the map of what must already be true:

- the ticket resolves to a live, unlocked partition;
- an e2e suite is configured (`settings.e2e` or `settings.suites.e2e`).
  Missing → configure one with `/acs:setup`; `workflows/ship.yaml` skips this
  step entirely until then (`when: e2e_configured`), so a hand run without it
  has nothing to write INTO;
- `test-cases.md` exists for the ticket. Missing → "run /acs:create-test-docs
  <id> first";
- `test-cases.md` lists at least one e2e case. Zero → nothing to write; the
  pointer is to re-run `/acs:create-test-docs <id>` if the ticket needs
  end-to-end coverage. Do NOT work around this by editing `test-cases.md`
  yourself — the case set is `/acs:create-test-docs`'s artifact, and the count
  the gate uses (`acs_lib.gate_inputs.e2e_case_count`) is the same one the case
  document's own checks pin.

There is no predecessor-completed check: order lives in `workflows/ship.yaml`,
not in this gate. In the declared order this step runs after `/acs:code`, so the
behaviour the suites drive normally exists; run out of order and you will be
writing suites against a product that cannot pass them yet — legitimate, but say
so in the report.

Parse the printed context JSON. Fields you will use:

- `ticket_id`, `ticket` — the resolved ticket; its title names the suites.
- `partition` — absolute path of `<workspace>/<repo-id>/<ticket-id>/`. Phase
  artifacts go in `<partition>/phases/create-e2e-tests/`.
- `checkout_root` — the consumer repo root; every suite path is repo-relative
  to it.
- `settings` — you need `suites` (the reserved `e2e` entry: its `command`,
  optional `setup`/`teardown`; `settings.e2e` is normalized into it at load
  time, so read `suites["e2e"]` and never the raw alias), `artifacts.tickets_path`
  (where `test-cases.md` lives), `quality_path`, `architecture_path`,
  `formats.branch_name`, `formats.commit_message`.
- `models` — per-role `{model, effort}` for planner/executor/verifier.
- `reconcile`, `handoff_summary`, `prior_run_status` — see Resume & reconcile.
- `post_hook` — absolute path to `post-create-e2e-tests.py`.

Throughout this file `<partition>` means the `partition` path from the context
JSON and `<id>` means `ticket_id` (e.g. `SHOP-123`).

## Branch — the suites are repo files

The e2e suites are part of the ticket's changeset and belong on the ticket
branch. Render `settings.formats.branch_name` (default
`"{type}/{ticket_id}-{slug}"`) with `{ticket_id}`, `{type}` (`ticket.type`),
`{slug}` (`acs.py slug --text "<title>"`) and `{external_key}`, then create or
reuse it:

```bash
git rev-parse --verify --quiet "<branch>" && git checkout "<branch>" || git checkout -b "<branch>"
```

The branch normally already exists — `/acs:code` ran on it. Reuse it; never
recreate or reset it, and never rebase it. Commit the suites with
`settings.formats.commit_message` (default `"{ticket_id} {summary}"`). Do NOT
push — `/acs:create-pr` pushes.

Unlike the ticket's documents, the suites are code: they are committed in the
repo whatever `artifacts.tickets_path` is set to. The docs-tree opt-out
(`tickets_path: null`) changes only where `test-cases.md` is READ from.

### The e2e cases — resolve them before anything else

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show --ticket <id>
```

`artifacts["test-cases.md"]` is the exact path the gate resolved — pass THAT
path to every subagent, and read it yourself now. The e2e cases are the rows of
its `## Cases` table whose `Type` cell is `e2e`; their `TC-<n>` ids are what
this run covers and what it reports as `cases_covered`. Count them with the
gate's own counter, so your idea of the work equals the gate's:

```bash
python3 -c "import sys; sys.path.insert(0, sys.argv[1]); import acs_lib; print(acs_lib.e2e_case_count(sys.argv[2]))" \
  "${CLAUDE_PLUGIN_ROOT}/hooks/scripts" "<test-cases path>"
```

The same `artifacts show` call reports `artifacts["plan.md"]`,
`artifacts["api-contract.md"]` and `artifacts["design.md"]` — read them when
they exist: the contract gives the exact shapes an e2e assertion checks, and the
plan names what the change actually built.

**A case may already have a test.** `/acs:code` writes a test per `TC-<n>` in
its own file map, naming the id in the test's docstring, and its executor is
told to cover an e2e flow its spec's Test plan names. So before planning
anything, grep the repo for the ids in scope — an existing test that already
drives the case end to end is ADOPTED (extended where the case asks for more,
left alone where it does not) and reported in `cases_covered`; writing a second
test for the same id is a duplicate suite, not coverage.

### The e2e location — derive it, never invent it

`settings.suites["e2e"]` carries a COMMAND, not a directory. Resolve where this
repo's e2e suites live, once, before planning, and state it in the plan's
`<constraints>`:

1. The existing e2e suites: find them (`git ls-files`, the harness's config
   file, the directories the command names). If the repo already has e2e tests,
   they define the location, the harness, the naming, the fixtures and the
   helpers — follow them exactly.
2. The e2e command itself: a runner config (`playwright.config.*`,
   `cypress.config.*`, a pytest path argument, a make target) names its test
   root. Read the config rather than guessing from the command string.
3. `<checkout_root>/<settings.architecture_path>/hld/project-structure.md` when
   it exists — the repo's declared layout.

If all three are silent — a configured command but no suite, no config and no
declared layout — do NOT invent a convention: that is a repo-structure decision.
Ask the user (User interaction) and record the answer in the clarification
ledger before any file is written.

**Naming.** Each suite file is named after the ticket, in the repo's existing
style — e.g. `<e2e root>/shop-123-csv-import.spec.ts`,
`<e2e root>/test_shop_123_csv_import.py`. One suite file per ticket is the
default; split into more only when the harness requires it (different fixtures,
different app entry points), and never one file per case.

**Traceability.** Every test in the suite carries its `TC-<n>` id in its name or
in a comment on its first line, so `/acs:run-e2e-tests` and any reader can map a
failure back to the case and the acceptance criterion behind it.

## Resume & reconcile

If `context.reconcile` is true (prior run `in_progress`/`failed`/`interrupted`/
`handed_off`), verify recorded progress against reality BEFORE continuing:

1. Read `<partition>/create-e2e-tests-state.json` (`runs[-1]` and `states`) and
   the phase artifacts under `<partition>/phases/create-e2e-tests/`.
2. Look at the repo: `git status` and `git log --oneline <branch>` show which
   suite files exist and which are already committed. A suite recorded written
   that is not on disk is not written; a suite on disk that is uncommitted is
   this run's to finish.
3. Re-read `test-cases.md` — its e2e rows may have changed since the prior run,
   and a suite covering a case that no longer exists is a suite to remove.
4. Continue from the first unfinished phase — planner artifact present but no
   suite → re-run execute against it; suites present but unverified → verify.
5. A resumed run reuses `<partition>/phases/create-e2e-tests/iter-1-plan.md` and
   never spawns a second planner; the plan phase runs (once) only when that
   artifact is absent.

If `context.handoff_summary` exists, read it plus
`<partition>/phases/create-e2e-tests/handoff-context.md` (when present), do a
light reconcile, and continue from where it points.

## Inputs — gather before planning

Read these yourself and name them by path in the planner's `<inputs>` (never
inline a file body):

1. `test-cases.md` — the e2e rows are the specification: preconditions, steps,
   expected result, and the criterion each proves.
2. The existing e2e suites, fixtures, helpers and harness config — the style
   this run writes in.
3. `plan.md` and `api-contract.md` when they exist — what was built, and the
   exact request/response shapes and error codes an assertion checks.
4. The product surface the cases drive: the routes, commands or screens, read
   from the code itself, so a selector or an endpoint in a test is one you have
   seen.
5. `<checkout_root>/<settings.quality_path>/` when it exists — the repo's test
   strategy, including what it says about e2e scope, determinism and runtime.
6. `settings.suites["e2e"]` — `command`, `setup`, `teardown`. The suites must be
   runnable by THAT command with no new runner, no new flag and no new
   dependency; needing one is a question for the user, not a silent addition.

## Reflection loop

Plan once, before the loop, then run execute → verify until the verifier
returns zero blocking findings or the cap is reached. The cap is a fixed **3**
in every lane — `/acs:create-e2e-tests` has no lane-driven verify depth.

**What an iteration counts.** One iteration is one execute → verify round; the
plan phase runs exactly once, before the loop, and is not part of any
iteration — the cap counts execute+verify rounds, not plan+execute+verify
triads.

Decomposition is YOURS alone — subagents never spawn subagents.

Messaging rules (`schemas/acs-messages.xsd`):

- Send each subagent one `<task skill="create-e2e-tests"
  phase="plan|execute|verify" ticket-id="<id>" iteration="n">` carrying
  `<objective>`, `<inputs>` (file refs) and `<constraints>`.
- Every phase's `<constraints>` carry `e2e_command` (and `e2e_setup` /
  `e2e_teardown` when configured), `e2e_root` (the location resolved above),
  the `TC-<n>` ids in scope, and
  `<constraint name="audience_style_profile">this repo's existing e2e suites</constraint>`.
- Validate EVERY message you send and receive:

  ```bash
  echo "<xml>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
  ```

  On invalid: re-request once with the validation error quoted; still invalid →
  fail the run and record the error in the result document's `errors`.
- Persist every phase's `<task>` and `<result>` to
  `<partition>/phases/create-e2e-tests/iter-<n>-<phase>.xml` at the phase
  boundary, BEFORE starting the next phase.
- Spawn subagents with the Agent tool: `acs:create-e2e-tests-planner`,
  `acs:create-e2e-tests-executor`, `acs:create-e2e-tests-verifier` — fall back
  to the un-namespaced name only if the runtime rejects the namespaced one.
  Apply `context.models.<role>.model` / `.effort` at spawn when not
  `"inherit"`; if the runtime rejects the model or effort, FAIL the run with
  that exact error — no silent fallback.

### Phase: plan (once, before the loop) — `acs:create-e2e-tests-planner`

Objective: from the e2e cases, the existing suites and the product surface,
decide the suite layout — which file(s), which test per `TC-<n>`, which
fixtures and setup each needs, what the assertion for each expected result
actually is, and what each case needs that the harness does not yet provide —
and write it to `<partition>/phases/create-e2e-tests/iter-1-plan.md`. The
planner reads and plans; its only write is that artifact.

If the planner returns `<questions>`, resolve them in User interaction BEFORE
executing, and carry the answers into the execute `<task>` via `<context>`.

### Phase: execute — `acs:create-e2e-tests-executor`

**Declare the file map before you spawn the executor** — the PreToolUse guard
enforces it, and an undeclared map means no enforcement at all:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" filemap set \
  --iteration <n> --task 1 --file <e2e root>/<suite file> --file <e2e root>/fixtures/<...>
```

Declare exactly the suite and fixture paths the plan lists — every one of them
under the resolved e2e location, including any existing suite file the plan
adopts — and NOTHING under the product's source tree.
That is the mechanical half of "this skill never writes product code": an
executor that finds it needs a source change returns `needs_input` naming the
file, and you take it to the user rather than widening the map. Re-declare
before each iteration's remediation executor; the guard reads the highest
declared iteration.

Objective: write the suites the plan lays out, in the repo's harness and style,
each test carrying its `TC-<n>` id, each assertion checking the case's stated
expected result. One suite per run, revised in place across iterations.

On iteration ≥ 2 the executor fixes every finding in `<context>` and nothing
else — no planner spawn in between.

### Phase: verify — `acs:create-e2e-tests-verifier`

Spawn `acs:create-e2e-tests-verifier` AFTER the suites are written, with
`<inputs>` of the suite files, the planner artifact, `test-cases.md`, the API
contract when it exists, and the existing suites it must match. It judges
fresh — never forward the executor's reasoning — and writes
`<partition>/phases/create-e2e-tests/iter-<n>-verify.md`.

The verifier RUNS the configured e2e command once (with `setup` and, always,
`teardown`) to prove the suites execute and are picked up by the harness, and
it reads the output with the distinction this skill turns on:

- **A wiring failure is a finding**: the suite is not collected, an import or
  syntax error, a missing fixture, a selector that matches nothing because it
  was invented, a test that passes without exercising anything.
- **A product failure is NOT a finding here** — the suite ran, drove the
  product, and the product did not do what the case says. Record it in the
  verify report and in the coordinator's `findings`; `/acs:run-e2e-tests` is the
  step that fails the pipeline on it, and `workflows/ship.yaml` relays that back
  to `/acs:code`. NEVER weaken, skip, or narrow a case's assertion to turn one
  green — that is the one failure mode this triad exists to prevent.

ALL blocking findings block — zero blocking findings = pass.
`status="completed"` means verification RAN; the empty `<findings>` is the
pass. Never conclude a pass the verifier did not report. On findings: persist
the verify output, then AUTOMATICALLY re-execute with every finding in the next
executor's `<context>`. After iteration 3 with findings remaining: stop with
final status `"failed"`, findings recorded, and the suites left as they are on
the branch (uncommitted work is not discarded silently — say where it is).

### Coverage check the coordinator runs before committing

Every e2e `TC-<n>` in `test-cases.md` must appear in a written suite. This is
$0 and deterministic — do it yourself:

```bash
grep -o 'TC-[0-9]\+' <e2e root>/<suite files> | sort -u
```

Compare that set with the e2e rows' ids. A missing id is a case with no test:
that is a blocking finding for the next iteration, never a note in the report.
An extra id (a test for a case that is not typed e2e) is a finding too — the
case set decides the level, not this skill.

### Commit

Once the verifier passes and the coverage check is clean, commit the suite and
fixture files on the ticket branch with `settings.formats.commit_message`.
Commit ONLY the paths in the file map; if `git status` shows anything else
changed, STOP and surface it — an unexpected modified file under the source tree
means the "never write product code" rule was breached and the run must not
hide it.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them in ONE grouped interaction (a
single AskUserQuestion containing all open questions as a numbered list), not
serial round-trips. Record each answer as its own `clarify.py add` entry (one
`C-<n>` per question, `--source` preserved), with
`clarify.py add --skill create-e2e-tests --question "..." --answer "..." --ticket <id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. When the user is unreachable, record the entry with
`--source assumption --rationale "..."` and state the same assumption in the
report.

The questions that belong here are structural, not stylistic: where e2e suites
live when the repo has none; a fixture, seed dataset or environment a case needs
that the harness cannot provide; a case whose preconditions no e2e run can
reach. A case that cannot be driven end to end is a `needs_input` outcome —
write the suites you can, leave the case out with the reason, and return the
question. Do not "cover" it with a test that asserts something weaker.

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Commit whatever suites already verified, flush
in-flight state plus soft context (user answers, harness gotchas, fixtures
added) to `<partition>/phases/create-e2e-tests/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, also on failure or handoff:

1. Write `<partition>/phases/create-e2e-tests/result.json` per the
   result-document contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "stop_reason": "verifier passed with zero findings on iteration 2; 2 e2e cases covered by 1 suite, committed",
     "states": {
       "suites_written": ["e2e/shop-123-csv-import.spec.ts"],
       "cases_covered": ["TC-5", "TC-6"]
     },
     "findings": [],
     "errors": []
   }
   ```

   Canonical `states` keys — EXACT names; `post-create-e2e-tests.py` documents
   them and the next step reads them:
   - `suites_written` (list): the repo-relative suite (and fixture) files this
     run wrote, as committed on the ticket branch. Files only — a suite you
     planned but did not write is not in this list.
   - `cases_covered` (list): the `TC-<n>` ids from `test-cases.md` those suites
     cover, exactly as the coverage check derived them. It must equal the set of
     e2e-typed cases for a completed run; anything less is a `needs_input` or
     `failed` run with the gap named.

   A product failure the verifier observed goes in `findings` (with the case id
   and what the product did), never into `states`: this run's verdict is about
   the suites, and `/acs:run-e2e-tests` owns the product verdict.

   On failure keep whatever is true: the suites actually written, the cases
   actually covered, the open findings, and the reason (iteration cap, needs
   input) in `stop_reason`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-e2e-tests.py" --ticket <id> --result-file <partition>/phases/create-e2e-tests/result.json
   ```

   If it exits non-zero, surface its stderr verbatim — the run is not closed
   until it succeeds.

3. Report:
   - Direct invocation: a compact summary — the suites written and where, the
     cases covered, whether the suites currently pass or fail and why (naming a
     product failure as a product failure), and the next step
     (`/acs:run-e2e-tests --for-ticket <id>`).
   - Under `/acs:ship`: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` ≤1 KB, `<artifacts>` naming the
     suite files, `<questions>` when `needs_input`, and
     `<next-step>/acs:run-e2e-tests --for-ticket <id></next-step>`. Validate it
     with `validate_xml.py` like every other message.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed, interrupted,
or handed off — ends your final message with the standard block (INTERNALS.md
"Completion report"), rendered only AFTER the post-hook succeeded. Same labels,
same order, `none` where empty; under `/acs:ship` your final message is the
`<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-e2e-tests · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: <n> suite file(s) under <e2e root>; cases covered TC-…; suite run: <passing / red on TC-… because …>
- **Findings**: <product failures, uncovered cases, open clarifications, or "none">
- **Artifacts**: <suite paths, partition phase artifacts, branch, commit>
- **Metrics**: iterations <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:run-e2e-tests --for-ticket <ticket-id>`
```
