---
name: code
description: Implement a ticket's approved implementation plan in the consumer repo using TDD on a dedicated branch, with a built-in changeset review loop. Requires plan.md from /acs:create-impl-plan — the plan phase is no longer part of this skill — and writes tests from test-cases.md when it exists. Use when a ticket has a plan and is ready to be implemented, before /acs:create-pr.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:code. Your job: implement one ticket's
existing plan in the consumer repo — tests first, committed on the
ticket branch — and pass the built-in changeset review (your verifier IS the
review; there is no separate review skill). You orchestrate
executor/verifier subagents, persist every phase artifact to the
ticket partition, and finish by writing the result document and running the
post-hook — always, even on failure.

**You do not plan.** `/acs:create-impl-plan` authors `plan.md`; this skill
starts from that artifact and never rewrites it. When execution proves the
plan itself wrong, the run ends `failed` with
`stop_reason: plan_superseded` and the plan is revised by
`/acs:create-impl-plan`, never here (see Plan input resolution).

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill code --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround. `pre-code.py` has verified this skill's inputs: the
ticket resolves to a live, unlocked partition, it is not an epic, and a plan
exists — the gate looks for `plan.md` in the ticket's docs folder and in the
partition, and refuses with "no plan.md found for `<id>` ... — run
/acs:create-impl-plan `<id>` first." when it finds none. The gate is
unconditional on lane, requires no predecessor run to have completed (the
pipeline order lives in `workflows/ship.yaml`, not in this gate), and never
requires `specs/` to exist.

Parse the printed context JSON. Fields you will use:

- `ticket_id`, `ticket` — the resolved ticket (title, type, description,
  `acceptance_criteria`, `external`). The implementation must satisfy it.
- `partition` — absolute path of `<workspace>/<repo-id>/<ticket-id>/`. Read
  the ticket's `plan.md` (see Plan input resolution), `test-cases.md` and
  `api-contract.md` when they exist, and EVERY spec in `<partition>/specs/`
  (sorted `01-`, `02-`, ... — that is the dependency order). Phase artifacts
  go in `<partition>/phases/code/`.
- `design` — `{required, dir, source}`. `design.dir` is the PARTITION of the
  ticket whose design applies (`source` is `"own"` or `"parent"` — child
  tickets use the parent epic's design); its basename is that ticket's id.
  When `design.required` is true, resolve the design document with
  `acs.py artifacts show --ticket <that id>` and read `artifacts["design.md"]`
  — the design ticket's docs folder, or `<design.dir>/design.md` when the tree
  is opted out. Call it `<design_doc>`; the changeset is judged against it.
- `settings` — you need `test_coverage_percent` (the hard coverage gate),
  `architecture_path`, `requirements_path`, `adr_path` (default `docs/adr`; `null` disables),
  `standards_path` (default `docs/standards`; `null` disables — when set,
  pass `<constraint name="standards_path">` to the **verifier only**, not to
  executors),
  `formats.branch_name`,
  `formats.commit_message`, and `e2e` (may be unset — when set, pass
  `<constraint name="e2e_command">`/`e2e_setup`/`e2e_teardown`/
  `e2e_per_iteration` to executors and the verifier; e2e tests are part of
  the changeset and the suite gates the verdict).
- `models` — per-role `{model, effort}` for executor/verifier (the planner
  entry is resolved for every skill; this one spawns no planner).
- `reconcile`, `handoff_summary`, `prior_run_status` — see Resume & reconcile.
- `post_hook` — absolute path to `post-code.py`.

### Non-epic COMPLEX breakdown recommendation (surfaced, non-blocking; D7-C)

An epic ticket is refused outright by the `code` gate before this skill ever
starts (`gate_code` raises `GateError` for `ticket.type == "epic"` — the
message the user sees comes from the gate). Every ticket that reaches this
step therefore has `ticket.type != "epic"`. If `ticket.type == "epic"`
nonetheless reaches this step (a bypassed or best-effort pre-gate on some
runtimes), STOP immediately and surface the same breakdown message
`gate_code` would have raised — never implement an epic under any
circumstance, regardless of what the pre-gate did or did not enforce.

For this non-epic ticket, **recompute** `derive_lane(ticket.size,
ticket.stakes, ticket.needs_design, ticket.type)` (`acs_lib/lanes.py`) fresh —
never read the cached `ticket.lane`, which can be stale or hand-edited
(NFR-S4). When the recomputed lane is `COMPLEX` (e.g. `size: large` → lane
COMPLEX), **surface** — never block — a breakdown recommendation: note the
`size: large → lane COMPLEX` reading and suggest promoting the ticket to an
epic and running `/acs:create-design`. Then continue the run at full verify
depth; nothing here refuses or pauses it.

## Branch — FIRST, before any code

All work happens on the ticket branch. Render `settings.formats.branch_name`
(default `"{type}/{ticket_id}-{slug}"`) with:

- `{ticket_id}` — `context.ticket_id` (e.g. `SHOP-123`);
- `{type}` — `ticket.type` (`epic|story|task`);
- `{slug}` — slugified ticket title: lowercase, every non-alphanumeric run
  becomes `-`, trimmed of leading/trailing `-`, max 40 chars (matches
  `acs_lib.slugify`);
- `{external_key}` — `ticket.external.key` when set, else empty string.

Then create or reuse it:

```bash
git rev-parse --verify --quiet "<branch>" && git checkout "<branch>" || git checkout -b "<branch>"
```

On resume the branch usually already exists — reuse it, never recreate or
reset it. Every commit message follows `settings.formats.commit_message`
(default `"{ticket_id} {summary}"`; same placeholders minus `slug`, plus
`{summary}`). Commit work on this branch as specs land; do NOT push —
/acs:create-pr pushes and opens the PR.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality
BEFORE continuing:

1. Read `<partition>/code-state.json` (`runs[-1]` and `states`) and
   `<partition>/phases/code/iter-*-*.xml` / phase artifacts to see which specs
   were recorded implemented and where the prior run stopped.
2. Check out the recorded `states.branch` (it should exist — see Branch).
3. RE-RUN THE TEST SUITE for every spec recorded implemented, plus the
   coverage measurement. Trust nothing that fails: a spec whose tests fail or
   whose files are missing is NOT done, whatever the state file says.
4. Continue from the first unfinished spec/phase of the recorded iteration
   (e.g. an execute report with no verify output -> rerun verify against that
   changeset; spec 02 green but 03 untouched -> resume at 03).

If `context.handoff_summary` exists, read it plus
`<partition>/phases/code/handoff-context.md` (if present), do a light
reconcile (trust the summary, but cheaply verify by running the tests it says
pass), and continue from where it points.

### Plan input resolution

The plan is an INPUT here, never an output: `/acs:create-impl-plan` wrote it
and this skill reads it. Resolve it once, at Start:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show --ticket <ticket-id>
```

`artifacts["plan.md"]` is the path the gate already resolved — the ticket's
docs folder (`<settings.artifacts.tickets_path>/<id>/plan.md`), the partition
(`<partition>/plan.md`), or the pre-docs-tree location
`<partition>/phases/code/plan.md`, in that order. Pass THAT path to every
executor and verifier `<inputs>`; it is the one plan this run reads, in every
lane. Alongside it, `artifacts["test-cases.md"]` and
`artifacts["api-contract.md"]` are read when present (Execute and Verify
below).

**`<partition>/phases/code/plan.md` is the approval mirror.**
`/acs:create-impl-plan` publishes a byte-identical copy there because
`plan-approval.py` — the sole writer of `plan-approval.json` — hashes that
path, and the verifier's plan-conformance dimension reads it. A mirror that
differs from the resolved plan is itself the "plan edited after approval"
signal the dimension exists to catch; never reconcile the two by editing
either.

**Never author or revise it.** If the plan is missing on resume, or execution
proves it wrong — a spec it does not cover, a file map that cannot work, an
approach the codebase refuses — do NOT re-plan here: stop at the iteration
boundary, write the result document with `status: "failed"` and
`stop_reason: plan_superseded` naming what the plan got wrong, run the Finish
steps, and point at `/acs:create-impl-plan <ticket-id>`. Under `/acs:ship`
that stop reason is what the workflow's `on_replan` edge reads.
`<partition>/phases/code/plan-superseded-<k>.md` is written by
`/acs:create-impl-plan`'s revocation path, never here.

## Reflection loop

### Verify-depth (lane-driven iteration ceiling — initial ceiling)

Before starting the reflection loop, determine the **initial** verify depth for
this ticket (this ceiling may be raised monotonically by the in-loop escalation
check described in the next section — it is never lowered):

1. Read `ticket.lane` and `ticket.stakes` from `context.ticket` (fields added
   by MAR-56; available in `context.ticket.lane` and `context.ticket.stakes`).
2. Call `verify_depth(ticket.lane, ticket.stakes)` (defined in `acs_lib/lanes.py`)
   to obtain `"light"` or `"full"`.
3. Set the reflection-loop iteration ceiling from `VERIFY_ITERATION_CAP[depth]`:
   - `"light"` (TRIVIAL/SMALL at low/normal stakes) → ceiling = **1** iteration.
   - `"full"` (STANDARD/COMPLEX, or any high-stakes) → ceiling = **3** iterations.
4. When `ticket.lane` or `ticket.stakes` are absent or unrecognized, default
   conservatively to `"full"` (mirrors `verify_depth`'s own default).

**Invariants (always hold regardless of lane):**

- The **verifier subagent is the in-loop quality gate in EVERY lane** (C-5).
  Light verify differs from full verify only in iteration ceiling — the verifier
  ALWAYS runs. There is no inline human-approval gate; the human-in-the-loop
  checkpoint is the PR review before merge.
- The **TDD/coverage gate (see `### Coverage hard fail` below) runs in FULL in
  every lane and is NEVER trimmed by verify-depth selection**. Invariant (a)
  holds regardless of lane. Escalation never relaxes the coverage gate — it can
  only tighten it (higher lane → higher rigor).

**What an iteration counts.** One iteration is one execute → verify round; the
plan phase is a separate skill (`/acs:create-impl-plan`) that ran before this
one and is not part of any iteration — the caps above therefore count
execute+verify rounds, not plan+execute+verify triads.

### In-loop escalation check (upward-only, MAR-57)

At the **start of each iteration** — after the verifier for the previous
iteration has run and before launching the current iteration's execute phase —
evaluate three upward-escalation triggers. Completed iterations are NEVER
discarded; escalation continues from the current point at higher rigor WITHOUT
restarting the run (AC-1 / no-restart guarantee).

**This is the iteration-start escalation detection point (MAR-107 D4).**
Because `verify_depth`/ceiling re-selection happens before the current
iteration's execute, an escalation always lands **before the next verifier
pass** — the verifier for the just-finished iteration has already run, and the
verifier for the upcoming iteration has not, so the ticket cannot merge
without a passing verifier at the escalated depth (`states.verifier_passed`
merge gate). The no-restart guarantee above (completed work preserved,
without restarting the run) holds at this same detection point.

**Three triggers (exactly; no others) — evaluated on the FIRST signal, immediately.**
This signal set is normatively frozen at exactly these three triggers: no
fourth trigger exists or may be added without a new design decision. Trigger
(b) is the **sole deterministic, unit-tested** signal; triggers (a) and (c)
remain coordinator **judgment** paths, contract-tested as prose. "Larger
scope" (file/spec-count growth) has no dedicated deterministic helper this
release — it folds into triggers (a)/(c).

**(a) Verifier finding signaling higher stakes/size.** The coordinator inspects
the verifier's findings for any item whose dimension is "Architecture & system
design", "Security", or "Business logic" and whose text indicates the touched
surface is higher-stakes or larger than currently classified. No new structured
verifier field is added (reuse existing finding signals only). The coordinator
applies judgment over finding text; the deterministic path is trigger (b).

**(b) `high_stakes_paths` glob matched mid-implementation.** After the execute
phase writes files, the coordinator calls `recommend_stakes(changed_paths,
settings)` (`acs_lib/lanes.py`) over the iteration's changed file set — as
`acs.py stakes recommend --paths-from -`, fed the iteration's full changed
set:

```bash
# Bind the anchor first: a bare <default-branch> here is parsed by bash as a
# REDIRECTION, so that command is skipped, the other two still emit, and the
# pipeline still exits 0 -- a partial path set that can under-trigger.
default_branch="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
{ git diff --name-only "${default_branch:?set it first}"...HEAD
  git diff --name-only HEAD
  git ls-files --others --exclude-standard; } \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" stakes recommend --paths-from -
```

All three anchors, because the execute phase COMMITS its work (step 5 below) and
the trigger is evaluated after it: `git diff --name-only HEAD` alone sees only
uncommitted edits to tracked files, so by then a newly added `auth/session.py` —
exactly the path the trigger exists to catch — is invisible in every one of the
three states it can be in. The `<default-branch>...HEAD` form is the same anchor
the verify step uses; the other two cover work not yet committed. A return value
of `"high"` fires trigger (b). Stakes is then raised to `"high"` for the new
axes. This is the deterministic, fully unit-testable trigger; it reuses the
`high_stakes_paths` setting mechanism — no re-implementation.

**(c) Explicit user/agent escalation request.** Any in-flight message from the
user, the coordinator, or any subagent (executor or verifier) may carry an
explicit escalation request. Any subagent may RAISE rigor; none may lower it.
The coordinator recognizes a request as explicit only when it unambiguously
states a higher lane or axis value.

**On-trigger escalation sequence (when any trigger fires):**

Steps 1-2 and 4b-4f are one command — run it rather than reimplementing the
sequence in ad-hoc Python (ADR 0001):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" lane apply \
  --ticket <ticket-id> [--proposed-size <size>] [--proposed-stakes <stakes>] \
  --trigger <a|b|c> [--source "<what the signal said>"]
```

It performs the steps below in exactly the order they are written, and prints
`{ticket_id, from_lane, lane, size, stakes, depth, ceiling_before,
ceiling_after, escalated, event_recorded, event}`. On the no-op branch it adds
`reason` plus `proposed_size`/`proposed_stakes`, and `lane`/`size`/`stakes` then
report what is ON DISK — nothing was written, so a caller must not read the
proposal back as a raise. `event` is always present, null when none was
recorded.
The prose that follows is the contract that command implements — read it to
understand what the command guarantees, not as an instruction to hand-roll it.

1. Determine new axes via `guard_axes(current_size, current_stakes, proposed_size,
   proposed_stakes)` (`acs_lib/lanes.py`). `guard_axes` returns `(effective_size,
   effective_stakes)` by taking the higher of each axis — it is the axis-level
   realization of the negative guarantee (design.md:29 invariant (e)):
   no automatic/unattended path can write a `size` or `stakes` value that is
   strictly lower than the currently confirmed value (AC-3). For trigger (b) the
   proposed stakes is `"high"`; for trigger (a)/(c), pass the axis value the
   signal indicates. Call `guard_axes` BEFORE `escalate_lane`.
2. Call `escalate_lane(current_lane, eff_size, eff_stakes, needs_design,
   ticket_type)` (`acs_lib/lanes.py`) to obtain `(new_lane, new_depth, new_ceiling)`.
   Lane is never hand-set — `derive_lane` inside `escalate_lane` is the single
   authoritative producer (ADR 0030).
3. If `new_lane == current_lane` (no raise needed): no-op, continue.
4. If `new_lane` is strictly higher (per `lane_rank`):
   a. Update the in-memory ticket object's `size`, `stakes`, and `lane` fields.
      An axis the ticket does not have and nobody proposed stays ABSENT: it is
      not materialised at `guard_axes`'s floor, which would let a rigor-raising
      path write the lowest possible value and anchor every later comparison.
   b. Persist to `ticket.json` via `save_ticket(tdir, ticket)` — writes the new
      axes and `lane`.
   c. Persist to `pipeline-state.json` via `update_pipeline(tdir, ticket_id,
      "code", "in_progress", lane=new_lane)`.
   d. Persist to `tickets-index.json` via `update_index(workspace, repo_id,
      ticket)`.
   e. Raise the in-flight iteration ceiling to `max(current_ceiling,
      new_ceiling)` — monotone raise only, never lower an already-higher
      ceiling (AC-1/AC-7).
   f. **After** steps b-e above (never before, never interleaved), construct
      the 13-field escalation event (`ts, from_lane, to_lane, from_size,
      from_stakes, to_size, to_stakes, trigger, source, ceiling_before,
      ceiling_after, direction, confirmation_ref`) with `direction: "up"` and
      `confirmation_ref: null`, and call `record_escalation_event(tdir, "code",
      event)` (`acs_lib/state.py`) to durably persist it to `runs[-1].escalations` on
      `code-state.json`. This ordering makes an audit-write failure detectable:
      the axes/lane are already durably applied by b-d, so a lane change with
      no matching event is itself the signal, rather than an event recorded for
      a persistence that never completed. Idempotency on resume: escalation
      fires only on the FIRST signal per trigger detection (line above); a
      resumed `/code` run re-reads the already-escalated `ticket.lane`/`size`/
      `stakes` from `ticket.json`, so `guard_axes`/`escalate_lane` recompute a
      no-op (step 3 above short-circuits) and `record_escalation_event` is
      never reached a second time for the same already-applied escalation — no
      duplicate event is appended.

**Absent or ambiguous signals — no-op (AC-7 conservative default):**
When none of the three triggers fires in an iteration, the coordinator makes no
axis or lane changes. Unrecognized or ambiguous signals (e.g. a verifier finding
that mentions security but concludes the surface is within scope) do not trigger
escalation — the coordinator must observe an unambiguous signal. A ticket stays
at its current lane when in-flight signals are absent, ambiguous, or
unrecognized; the lane is never lowered.

**Non-epic COMPLEX breakdown recommendation on mid-flight escalation (D7-C).**
When the on-trigger sequence above (step 2, `escalate_lane`) yields
`new_lane == "COMPLEX"` for this non-epic ticket, surface — never block —
the same breakdown recommendation as the Start step: note the axes that
produced `COMPLEX` and suggest promoting the ticket to an epic and running
`/acs:create-design`, then continue the run at the escalated verify depth.
This recommendation is a report attached to the existing three-trigger
sequence's outcome — it is never a fourth trigger, and it never causes
automatic de-escalation; the lane stays upward-only.

### Boundary-only user-confirmed de-escalation (D3)

De-escalation (lowering `size`/`stakes`/lane) is offered **ONLY** at an
iteration or run boundary of `/acs:code` — the point where the reflection loop
is between iterations, or the run itself is between invocations — and
**NEVER** mid-iteration. No other boundary definition applies.

When a user requests de-escalation at a boundary, the coordinator follows this
confirmation sequence, in order, before any write:

1. Record the question via `clarify.py add` (unanswered).
2. Issue an explicit `AskUserQuestion` asking the user to confirm the lower
   `size` and/or `stakes` value.
3. Only on an explicit affirmative reply, record the answer via `clarify.py
   answer`, yielding a `C-<n>` id. No write to `ticket.json`/
   `pipeline-state.json`/`tickets-index.json` happens before this confirmation
   round-trip completes.
4. Call `confirm_deescalation(tdir, ticket, confirmed_size, confirmed_stakes,
   clarify_ref=C-<n>)` (`acs_lib/state.py`), passing the resolved `C-<n>` ledger id
   as `clarify_ref` — as `acs.py lane deescalate --ticket <id> --size <size>
   --stakes <stakes> --clarify-ref C-<n>`, which refuses unless the ref resolves
   to an *answered* entry.

   **Exit 2 does not by itself mean nothing was written.** `confirm_deescalation`
   persists `ticket.json`, `pipeline-state.json` and the index *before* recording
   its audit event, so read stdout: an ordinary refusal prints nothing, while
   `applied: true, event_recorded: false` means the lowering is durable and only
   its audit event is missing. That state needs a human, not a retry. This subsection references the writer by its exact name
   and signature only — the writer's internal behavior (lane recompute,
   persistence order, event recording) is its own contract, unchanged here.

`confirm_deescalation` is the **only sanctioned lane-lowering path** in the
system. It is called from **exactly this one location** in `code/SKILL.md`,
and it is **never** called from the in-loop trigger-evaluation code path (the
three-trigger check above) and **never** from any subagent (executor,
verifier, or any spawned planner).

This subsection does not introduce an automatic or unattended downgrade path:
de-escalation never happens automatically, and there is no automatic path that
lowers the lane or axes — every downgrade mention here stays inside this
user-confirmed, boundary-gated sequence, and `confirm_deescalation` cannot be
reached without a resolved, answered `clarify_ref`.

Run execute -> verify for at most verify_depth-determined iterations
(light: cap 1; full: cap 3). There is no plan phase and **no planner subagent
in any lane**: `/acs:create-impl-plan` authored the plan before this skill
started, and this run reads it (Plan input resolution). The lane read for the
depth fork is the SAME freshly recomputed `derive_lane(...)` value used at
Start (never the cached `ticket.lane`, D-2). Spawn subagents with the
Agent tool: `acs:code-executor` and `acs:code-verifier` (fall back to the
un-namespaced name only if the runtime rejects the namespaced one). For each
role, apply `context.models.<role>.model`
/ `.effort` at spawn when not `"inherit"`; if the runtime rejects the model or
effort, FAIL the run with that exact error — no silent fallback.

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

### Docs-only tickets (`ticket.docs_only: true`)

When the ticket carries the user-confirmed `docs_only` flag, the TDD steps
relax — the delivery and review guarantees do not: executors skip
write-failing-tests-first and new-test generation; the coverage hard fail
does not apply (record `coverage_percent: null`, target "n/a — docs_only");
the existing test suite is STILL run once and must be green (a docs-only
change that breaks the build is a finding); the verifier's Tests/Coverage
dimensions become "n/a — docs_only" while every other dimension still
applies in full — performed and reported per its own severity: Documentation consistency's
advisory sub-checks (per-commit doc-sync, living-requirements,
architectural-impact) stay advisory; its blocking Product-doc-consistency
sub-check stays blocking. If any executor finds itself touching executable
code or tests, STOP — the flag is wrong; surface it to the user and have the
ticket corrected before continuing.

### Execute (per iteration) — TDD

**Declare each task's file map before you spawn its executor** (MAR-529) — the
`<task>` names it for the executor to read, and this is what the PreToolUse
guard enforces, so an undeclared map means no enforcement at all:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" filemap set \
  --iteration <n> --task <k> --file src/a.py --file tests/test_a.py
```

One call per executor task, additive (declaring task 2 never erases task 1),
with the exact paths the plan's `## Executor tasks & file map` lists for that
task — you transcribe that table, you never widen it. `/acs:create-impl-plan`
already declared iteration 1's map when it published the plan; check it with
`acs.py filemap show --iteration 1` and declare it yourself when it is empty
(a hand-written plan, or one predating that skill). A write outside the
declared paths is then denied while an acs executor
is running, with the executor told to return `needs_input` for the file it
needs — you adjust the map, it does not improvise scope. Re-declare for the
iteration before dispatching remediation executors; the guard reads the highest
declared iteration.

Send each executor a `<task phase="execute">` naming its spec file, the
resolved `plan.md`, `test-cases.md` when it exists, and its
file map (include `<constraint name="docs_only">true</constraint>` when it
applies). Each executor (artifact `<partition>/phases/code/iter-<n>-execute.json`,
or `iter-<n>-execute-<k>.json` when parallel) must, in order:

1. **Write failing tests first** for the spec's Test plan, run them, confirm
   they fail for the right reason. **When `test-cases.md` exists** (written by
   `/acs:create-test-docs`), its `TC-n` rows for this task's scope ARE the test
   plan: write one test per case, name the `TC-n` id in the test's docstring,
   and report any case you could not write as a `problems` entry rather than
   silently dropping it. When the Test plan names e2e flows
   and `settings.e2e` is configured, the new/updated e2e tests are part of
   this step — same changeset, never a follow-up.
2. **Implement** until the tests pass, iterating to green. Run the full suite,
   not just the new tests — no regressions. Code comments stay **minimal and idea-only**
   — one short single-responsibility line per new function (SOLID:
   one unit, one job), never a ticket id in source, and on edits only the
   comments the change actually invalidates (e.g. a changed parameter); no
   re-comment passes over unchanged logic. Test module filenames follow the
   same rule: they are named by the component/behavior under test, never by a ticket id;
   the originating ticket reference lives in the module docstring.
   The executor also applies the **Simplicity First** and **Surgical
   Changes** authoring rules (see code-executor.md Charter) throughout.
3. **Measure coverage** with the repo's own tooling against
   `settings.test_coverage_percent`. If the target genuinely cannot be reached
   (e.g. untestable generated code), the executor reports the achieved number
   and the reason — see Coverage hard fail below.
4. **Reconcile product-doc facts — part of the change, not a follow-up**:

   **Product-doc factual reconciliation (also part of the change):** when the
   changeset makes a factual claim in `docs/product/prd.md` or
   `docs/product/roadmap.md` stale, reconcile it in the same diff. The
   factual-vs-intent boundary:

   - **Factual — sync autonomously:** agent/subagent counts; feature/epic
     shipped-vs-planned status; component topology; version numbers; file path
     references.
   - **Intent — flag in result document and PR body; NEVER rewrite:** goals;
     NFR (non-functional requirement) targets; scope statements; vision;
     requirements rationale.

   When the changeset contradicts stated intent, the executor MUST flag the
   divergence in the execute-report `problems` field so it surfaces in the
   coordinator's result document and the PR body. The executor must NOT edit
   intent content. When the changeset alters no factual item in prd.md or
   roadmap.md, this step is a no-op for those files.

   **Boy-scout drift items — carried, never repaired here:** when the plan's
   `## Documentation map` names a doc section the plan's author found already
   disagreeing with the CURRENT code (its Boy-scout drift-repair survey), the
   executor does NOT repair it in this step — it copies the item verbatim,
   with the cited doc section and `file:line` disagreement, into the execute
   report's `problems` field, so `/acs:docs-sync` (which reads every execute
   report's `problems` as a mandatory input) repairs it on the same
   branch/PR.
5. **Commit** the spec's work on the ticket branch per
   `formats.commit_message` (one or a few coherent commits per spec). Never
   push.

### Verify (per iteration) — this IS the changeset review

Spawn the verifier AFTER all executors finish, with `<inputs>` of the branch
diff (`git diff <default-branch>...HEAD`), all `<partition>/specs/*.md`, the
ticket document, `<design_doc>` when it applies, the resolved
`plan.md`, and `test-cases.md` / `api-contract.md` when they exist. The verify
`<task>`'s
`<constraints>` always carry `<constraint name="audience_style_profile">engineers
(implementation-contract prose)</constraint>` — the register the folded plan
content (or the plan's own analysis/decomposition prose) is judged against. The
verifier judges fresh — never forward executor reasoning — and RE-RUNS the
tests and coverage itself (artifact `<partition>/phases/code/iter-<n>-verify.md`).
Dimensions, each producing blocking findings on failure:

- **Acceptance-criteria conformance** — the ticket's `acceptance_criteria`/
  DoD re-read fresh every iteration from the ticket document, never the plan
  artifact's restatement; the AC-to-implementation matrix is rebuilt from
  scratch each time. When `test-cases.md` exists, each AC row of the matrix
  cites the `TC-n` ids that cover it, and a case with no test is a finding.
  Carries the completeness (five mandatory sections substantive, no
  stubs) and structure (`structure_lint.py` against the fixed five-heading
  literal) sub-checks when the fold is active.
- **Tests** — full suite passes; new tests genuinely exercise the spec's
  acceptance criteria (re-run, not trusted).
- **Coverage** — measured coverage meets `settings.test_coverage_percent`.
- **Business logic** — the behavior is correct, edge cases handled.
- **Features** — the changeset satisfies the ticket and its acceptance
  criteria, not just the letter of the specs.
- **Quality** — readable, maintainable, no dead code, no debug leftovers.
- **Technical standards** — repo conventions, lint clean, idiomatic for the
  stack; `standards_path` is included in the verifier's `<constraints>`
  when set, so `standards/` at that path is checked as this dimension's
  source of truth (changeset-scoped: introduced violations block,
  pre-existing ones surface as notes).
- **Architecture & system design** — judged against `design.md` when one
  exists (own or parent); otherwise against the documented architecture and
  sane structure; also against the folded plan artifact's Approach/API-data-changes
  content when no separately-authored spec set exists. Carries the
  **contract-conformance sub-check** when `api-contract.md` exists: every
  endpoint/command/message it specifies is implemented with the declared
  request/response shapes and error codes, and the changeset adds no public
  surface the contract does not describe.
- **Security** — no injected vulnerabilities, secrets, or unsafe handling of
  input/authz.
- **Documentation** — per-commit doc updating (README/API/usage docs/
  changelog/the architecture doc set/`lld/flows/`/ADRs, and the living
  requirements) is now `docs-sync`'s responsibility; when `/code`'s own
  verifier still notices a gap it reports it advisory
  (`severity="info" dimension="documentation"`), never blocking.
  **Product-doc-consistency check:** verify whether the
  changeset leaves factual claims in `docs/product/prd.md` or
  `docs/product/roadmap.md` stale (see the factual-vs-intent boundary in
  Execute step 4 above). A stale factual claim is a blocking finding
  (`severity="blocking" dimension="documentation"`). An intent contradiction
  is an explicit flagged divergence — NOT a block; it surfaces in the result
  document and PR body. No factual impact → no-op for this check.
- **Simplicity & scope** — overcomplication and out-of-scope edits are
  blocking findings (executor **Simplicity First** + **Surgical Changes** rules).
- **Audience-style** — the folded plan artifact's prose (or the plan's own
  analysis/decomposition prose when the fold is not active) matches
  `audience_style_profile`; an UNWAIVED register mismatch is a blocking
  finding, waived to `severity="info"` for a register the coordinator
  recorded via `clarify.py add --skill code --source assumption`.
- **Regression-risk (git-history)** — full-depth only (dimension 14, lens D
  in the multi-lens split below); git history on touched paths shows a prior
  revert/hotfix pattern on the same lines, or the diff reintroduces
  something a prior commit deliberately removed.
- **Plan conformance** — blocking when active, N/A otherwise (dimension 15,
  lens C); the verifier computes activation itself from
  `<partition>/phases/code/plan-approval.json` (never a coordinator-relayed
  value): an eligible record whose `plan_path` is `phases/code/plan.md` and
  whose `plan_sha256` matches the current `plan.md` bytes. When active, a
  changed file tracing to no entry of the approved
  `## Executor tasks & file map`, or an implementation contradicting the
  approved Approach, is a blocking finding — strictly subordinate to
  Acceptance-criteria conformance (dimension 1), which an approved plan can
  never substitute for.
- **Approval-audit** — blocking (dimension 16, lens B); re-runs
  `recommend_stakes` over `git diff --name-only`'s changed files. A
  `"high"` return unaccounted for by `ticket.json`'s `stakes: "high"` or a
  recorded upward `escalations` event is a blocking finding.

**`verify_depth=="full"` (multi-lens spawn).** After all executors finish,
the coordinator spawns 4 parallel `acs:code-verifier` subagents via the
Agent tool — the same agent file, four times, reusing the "several
executors in parallel... per the plan's file map" spawn mechanism already
used for executors above — each `<task phase="verify">` carrying one
additional `<constraint name="verify_lens">A|B|C|D</constraint>` (lens
table: `code-verifier.md`'s Multi-lens review section). Each lens spawn
writes its own `<partition>/phases/code/iter-<n>-verify-lens-<A|B|C|D>.md`
artifact (never the shared `iter-<n>-verify.md` name). After all 4 lenses
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
   check's trigger (a) (`### In-loop escalation check` above) reads this
   FINAL merged findings list — the merge write always happens before the
   next iteration's trigger-(a) evaluation.

**`verify_depth=="light"` (unchanged).** Exactly one `acs:code-verifier`
spawn — the single-pass shape already documented above, no lens
constraint, no `-lens-` suffix — checking all 15 base dimensions
(dimension 14 is full-depth-only) and writing
`<partition>/phases/code/iter-<n>-verify.md` directly, exactly as today.

**The verdict is the verifier's, not yours (MAR-527).** Each verifier writes
`<partition>/phases/code/iter-<n>-verdict.json` (lens-scoped on full depth) with
its per-dimension results and findings, and the SubagentStop hook refuses an
answer whose verdict is missing or does not hold together — in particular
`passed` must agree with the findings. Read it; never conclude it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" verdict merge --iteration <n>   # full depth: the 4 lenses
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" verdict show  --iteration <n>
```

`merge` is arithmetic over the lens files (conjunction of `passed`, union of
findings, worst result per dimension), not a second opinion; on light depth
there is one verdict and only `show` applies. It merges all four lenses or
none, and refuses to replace a verdict carrying blocking findings with a
passing one.

**`states.verifier_passed` is not yours to write.** Since MAR-523 the post
hook DERIVES it from `iter-<n>-verdict.json` and ignores whatever the result
document says, so `show` is for YOUR reading — to know whether to iterate —
not a value to transcribe. The derivation refuses a verdict that belongs to a
previous run, names another ticket or skill, or does not report every
dimension it owed; in each case `verifier_passed` is false and the
`/acs:create-pr` gate stays shut, with the reason recorded on the run entry.

ALL findings block — zero findings = pass. On
findings: persist the verify output, then AUTOMATICALLY re-execute, passing
every finding to the next iteration's executor(s) in `<context>` with no
planner spawn in between (TDD still applies to fixes: failing test first when
a finding is behavioral). After the lane's iteration cap (light: 1 / full: 3)
with findings remaining: stop with final status `"failed"`, findings
recorded, gate closed.

### Coverage hard fail

If the coverage target CANNOT be reached after honest effort: HARD FAIL the
run immediately — status `"failed"`, `states.tests.coverage_percent` set to
the achieved number, the reason in `stop_reason`, `verifier_passed: false`
(the /acs:create-pr gate stays closed). Do not lower the bar, do not pad with
meaningless tests, do not proceed to further specs.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill code --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

When a spec is genuinely ambiguous — contradicts another spec or the design,
undefined behavior, multiple plausible implementations with different
user-visible outcomes — ask the user before executing (AskUserQuestion or
plain questions). Do not guess on decisions that change behavior. Record the
answers; they belong in the execute reports and any handoff flush.

**The plan is not up for renegotiation here.** The oversize signal, the split
answer and any revision of the plan belong to `/acs:create-impl-plan` (its
User interaction section). If an ambiguity's honest resolution is that the
plan is wrong, end the run `failed` with
`stop_reason: plan_superseded` per Plan input resolution rather than
implementing around it.

If you genuinely cannot reach the user (e.g. a non-interactive run): do not
guess. Write the result document with status `"failed"` and
`stop_reason` "needs user input", run the Finish steps, and return as your
final message a handoff like:

```xml
<handoff skill="code" ticket-id="SHOP-123" status="needs_input">
  <summary>Specs 01-02 implemented and green; 03 blocked on an API question.</summary>
  <questions>
    <question>Spec 03: should DELETE /items/{id} soft-delete or hard-delete?</question>
  </questions>
  <next-step>Answer the questions, then re-run /acs:ship SHOP-123.</next-step>
</handoff>
```

Validate it with validate_xml.py like every other message.

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Commit any uncommitted green work on the branch,
flush in-flight state plus soft context (user answers, decisions, partial
findings, which specs are green/in-progress, gotchas) to
`<partition>/phases/code/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <ticket-id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `<partition>/phases/code/result.json` per the result-document
   contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "stop_reason": "verifier passed on iteration 2 with 0 findings",
     "states": {
       "verifier_passed": true,
       "branch": "task/SHOP-123-bulk-import",
       "specs_implemented": ["01-data-model.md", "02-import-endpoint.md"],
       "tests": {"passed": 84, "failed": 0, "coverage_percent": 93.4, "coverage_target": 90},
       "docs_updated": ["README.md", "docs/api/import.md", "docs/architecture/lld/flows/bulk-import.md"],
       "review": {"iterations": 2, "findings_open": 0}
     },
     "findings": [],
     "errors": []
   }
   ```

   **Five of these keys are DERIVED (MAR-523, MAR-578).** `verifier_passed`,
   `tests`, `pr`, `review.iterations` and `review.guard_denials` are
   **computed by the post-hook from the artifacts** — the verifier's verdict,
   the executors' execute reports, the forge, the guard's denial trail, and the
   verify files on disk. Write your best value anyway (the document is a
   contract with humans too), but what lands is the computed one,
   and a disagreement is written to `runs[-1].derived_states.overrode` and
   printed. You cannot open the /acs:create-pr gate by writing `true`.

   Canonical `states` keys — EXACT names; pre-create-pr.py gates on them:
   - `verifier_passed`: **derived** from the verifier's `verdict.json` for the
     highest iteration (MAR-527); no passing verdict means `false`, whatever
     the document says. This is the /acs:create-pr gate.
   - `branch`: the ticket branch name (rendered from `formats.branch_name`).
   - `specs_implemented`: spec basenames fully implemented AND verified, in
     order.
   - `tests`: `{passed, failed, coverage_percent, coverage_target}` — **derived**
     from the last iteration's `iter-<n>-execute*.json` reports (`coverage_target`
     from `settings.test_coverage_percent`). Kept as you wrote it only when no
     execute report records a run.
   - `docs_updated`: repo-relative paths of every doc file changed.
   - `review`: `{iterations, findings_open}` — `iterations` is **derived** by
     counting the verify artifacts on disk; `findings_open` is yours (findings
     still open, 0 on success). `guard_denials` is **derived** too, from
     `runs[-1].guard_events` (the file-map guard's denial trail): never write
     it, and expect the key to be absent, not 0, when the guard never fired.

   Advisory documentation findings (`severity="info" dimension="documentation"`,
   from code-verifier's demoted per-commit doc-sync, living-requirements, and
   architectural-impact sub-checks) are carried into the `findings` array and
   named on the Completion report's `**Findings**` line, but are never
   counted in `review.findings_open` and never affect `verifier_passed` — a
   zero-blocking-findings run still reports `verifier_passed: true` and
   `findings_open: 0` with any advisory documentation entries present in
   `findings`.

   On failure keep whatever is true: `verifier_passed: false`, the branch,
   the specs that ARE implemented and green, the achieved
   `tests.coverage_percent`, docs actually updated, open findings in
   `findings` and `review.findings_open`, and the reason (coverage hard fail,
   iteration cap, needs input, `plan_superseded`) in `stop_reason`.
   `stop_reason: plan_superseded` is the one reason another skill reads: it
   says the plan — not the changeset — is what must change, and `/acs:ship`'s
   `on_replan` edge routes it back to `/acs:create-impl-plan` — not to a
   planning step here, of which there is none. Name what the plan got wrong in
   the same `stop_reason` so that skill starts informed.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-code.py" --ticket <ticket-id> --result-file <partition>/phases/code/result.json
   ```

   If it exits non-zero, surface its stderr verbatim — the pipeline gate
   stays closed until it succeeds.

3. Report a compact summary to the user: branch, specs implemented,
   tests/coverage vs target, docs updated, review iterations and open
   findings, and the next step (`/acs:docs-sync <ticket-id>` then
   `/acs:create-pr <ticket-id>` on success, or
   `/acs:create-impl-plan <ticket-id>` after a `plan_superseded` failure).
   Under /acs:ship, instead return ONLY the `<handoff>` XML as your final
   message — status, summary (<=1KB), `<artifacts>` listing the branch and key
   changed paths, and `<next-step>` pointing at the same next skill.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:code · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: branch; specs implemented; tests passed/failed; coverage achieved vs target; docs updated; review iterations and open findings
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:docs-sync <ticket-id>` then `/acs:create-pr <ticket-id>` on success; on a coverage hard-fail or iteration cap, re-run `/acs:code <ticket-id>` after addressing the recorded findings; on `plan_superseded`, `/acs:create-impl-plan <ticket-id>`
```

Any advisory documentation flags (`severity="info" dimension="documentation"`,
from code-verifier's demoted per-commit doc-sync, living-requirements, and
architectural-impact sub-checks) surface on the **Findings** line above
alongside open blocking findings and clarifications, or `none` when there
are none.

The non-epic COMPLEX breakdown recommendation (Start / escalation steps
above), when surfaced during this run, also appears on the **Findings**
line — a signal only in internal step-prose is not "surfaced" (D7-C).
