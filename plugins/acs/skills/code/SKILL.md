---
name: code
description: Implement a ticket's specs in the consumer repo using TDD on a dedicated branch, with a built-in changeset review loop. Specs are read from <partition>/specs/ when already present, or self-authored as part of the plan phase when not. Use once /acs:create-ticket (and /acs:create-design when required) has completed and before /acs:create-pr, when a ticket is ready to be implemented.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:code. Your job: implement every spec of one
ticket in the consumer repo — tests first, committed on the
ticket branch — and pass the built-in changeset review (your verifier IS the
review; there is no separate review skill). You orchestrate
planner/executor/verifier subagents, persist every phase artifact to the
ticket partition, and finish by writing the result document and running the
post-hook — always, even on failure.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill code --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround (pre-code.py has verified the gate precondition: that
/acs:create-ticket has completed and that the ticket is not an epic — the
gate is unconditional on lane and never requires `specs/` to exist. Whether
`<partition>/specs/` already has content is discovered by the planner below,
on every lane, not asserted by the gate).

Parse the printed context JSON. Fields you will use:

- `ticket_id`, `ticket` — the resolved ticket (title, type, description,
  `acceptance_criteria`, `external`). The implementation must satisfy it.
- `partition` — absolute path of `<workspace>/<repo-id>/<ticket-id>/`. Read
  EVERY spec in `<partition>/specs/` (sorted `01-`, `02-`, ... — that is the
  dependency order) plus `<partition>/ticket.json`. Phase artifacts go in
  `<partition>/phases/code/`.
- `design` — `{required, dir, source}`. When `design.required` is true, read
  `<design.dir>/design.md` (`source` is `"own"` or `"parent"` — child tickets
  use the parent epic's design); the changeset is judged against it.
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
- `models` — per-role `{model, effort}` for planner/executor/verifier.
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
   (e.g. plan persisted but no execute output -> rerun execute against that
   plan; spec 02 green but 03 untouched -> resume at 03).

If `context.handoff_summary` exists, read it plus
`<partition>/phases/code/handoff-context.md` (if present), do a light
reconcile (trust the summary, but cheaply verify by running the tests it says
pass), and continue from where it points.

### Plan artifact resolution

The plan artifact is `<partition>/phases/code/plan.md`, written and read by
the coordinator, the planner, the executor, and the verifier. This is the
only name or path ever read or written for the plan artifact, in every
lane, on every run.

**Fresh run.** When no plan artifact exists yet, read and write only
`plan.md`; a fresh run never creates a new iteration-numbered plan file.

**Resume.** If `plan.md` is absent on resume, that is treated the same as
any other missing or incomplete phase artifact under "Resume & reconcile"
above — re-derive from what actually exists rather than fabricating a plan.
There is no other name for this artifact to fall back to.

**Reservation.** `<partition>/phases/code/plan-superseded-<k>.md` is the
plan-revocation path's superseded-plan artifact — see the Plan revocation
subsection below (after Plan approval) for when it is written and read.

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
plan phase runs exactly once, before the loop starts, and is not part of any
iteration — the caps above therefore count execute+verify rounds, not
plan+execute+verify triads.

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
`acs.py stakes recommend --paths-from -`, fed `git diff --name-only`. A return value
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
`{escalated, event_recorded, lane, size, stakes, ceiling_before, ceiling_after,
event}`. `escalated: false` means step 3's no-op fired and nothing was written.
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
   --stakes <stakes> --clarify-ref C-<n>`, which refuses (exit 2, no write)
   unless the ref resolves to an *answered* entry. This subsection references the writer by its exact name
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

Plan once, before the loop, then run execute -> verify for at most
verify_depth-determined iterations (light: cap 1; full: cap 3). **On
STANDARD/COMPLEX**, exactly one `acs:code-planner` subagent is spawned across
the whole run, however many iterations the loop uses. **On TRIVIAL/SMALL**
(MAR-72), the coordinator authors `<partition>/phases/code/plan.md` itself at
the Plan step below — zero `acs:code-planner` spawns on those lanes, every
run. The lane read for this fork is the SAME freshly recomputed
`derive_lane(...)` value used at Start (never the cached `ticket.lane`,
D-2). Spawn subagents with the
Agent tool: `acs:code-planner` (STANDARD/COMPLEX only), `acs:code-executor`,
`acs:code-verifier` (fall back to the un-namespaced name only if the runtime
rejects the namespaced one). For each role, apply `context.models.<role>.model`
/ `.effort` at spawn when not `"inherit"`; if the runtime rejects the model or
effort, FAIL the run with that exact error — no silent fallback.

Messaging rules (schemas/acs-messages.xsd):

- Send each subagent one `<task skill="code" phase="plan|execute|verify"
  ticket-id="<id>" iteration="n">` containing `<objective>`, `<inputs>` (file
  refs: spec files, ticket.json, design.md when it applies, repo paths), and
  `<constraints>`. The subagent returns a `<result>` as its final content.
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

### Plan (once, before the loop)

**Lane fork (D-1/D-2, MAR-72).** This step forks on the SAME freshly
recomputed lane used at Start — `derive_lane(ticket.size, ticket.stakes,
ticket.needs_design, ticket.type)`, never the cached `ticket.lane` (D-2).

**STANDARD/COMPLEX — unchanged from MAR-71.** Task the planner with
`<inputs>` of all `<partition>/specs/*.md`, `<partition>/ticket.json`,
`<design.dir>/design.md` when `design.required`, and the relevant
consumer-repo source/docs. The planner returns (artifact:
`<partition>/phases/code/plan.md`):

**Spec authoring fold (`specs/` absent or empty, every lane)**

Before producing the standard plan content, check whether
`<partition>/specs/` already has `.md` content.

When `<partition>/specs/` is empty or absent — on EVERY lane, no lane check —
the plan's author (the code-planner on STANDARD/COMPLEX, the coordinator on
TRIVIAL/SMALL, MAR-72) ADDITIONALLY produces, as part of the plan artifact
(`<partition>/phases/code/plan.md`), the spec content a standalone
create-spec planner would once have produced. This content covers, in order:

- **Scope** — what the ticket delivers; acceptance criteria quoted verbatim.
- **Approach** — solution shape at contract level (components, interfaces,
  algorithms, error handling); indicative paths only.
- **API/data changes** — endpoints, schemas, contracts, migrations, config;
  documentation impact (which consumer-repo docs the change touches).
- **Test plan** — every `ticket.acceptance_criteria` entry MUST map to at
  least one test the plan will write; the coverage target
  (`settings.test_coverage_percent`) stated explicitly; e2e impact stated.
- **Out of scope** — adjacent work excluded.

**Oversize signal pointer.** `code-planner.md`'s charter item 2 also
compares this decomposition against the reviewable-diff bar; when it fires,
the split seams recorded above are what `/acs:create-ticket split` reads
(see User interaction for the split-answer termination).

**Mandatory clauses** (both MUST appear verbatim in the plan artifact):

- "no separate /acs:create-spec invocation and no separate create-spec planner
  subagent" (AC-3)
- "every ticket.acceptance_criteria entry maps to at least one test the folded
  plan will write" (AC-4)

If specs already exist, the fold does NOT activate — the plan's author reads
the existing specs normally, on every lane. The fold only activates when
`<partition>/specs/` is absent or empty.

This fold does NOT alter the execute or verify phases. The existing
`### Coverage hard fail` block (AC-5) and the existing `### Verify-depth`
block (AC-6) apply unchanged in every lane; see those sections.

- Analysis of every spec: implementation order (follow the spec numbering),
  ambiguities and explicit clarifying questions (surface these — see User
  interaction — before executing).
- The decomposition: typically ONE executor task per spec, each listing the
  exact repo files it will touch (source, tests, docs) — this file map decides
  whether executors may run in parallel.
- The test strategy per spec: which failing tests to write first, the repo's
  test/coverage tooling and the exact commands to run them, how
  `settings.test_coverage_percent` will be measured.
- The documentation map: whether any factual claims in `docs/product/prd.md`
  or `docs/product/roadmap.md` are made stale by the change (factual items:
  agent/subagent counts, shipped-vs-planned status, topology, version numbers,
  file path references) — `/acs:docs-sync` independently re-derives every
  other doc-delta (README/API/usage/changelog, the architecture doc set, ADRs)
  from the diff after `/code` completes.
  The planner also performs a bounded, touched-area ADR-0012 doc-graph-gap
  check (`code-planner.md`'s item 4, edges E1-E4) — not the full shared
  design-time step `create-design`'s planner runs — riding the same
  `problems` carrier as the existing Boy-scout drift item.
- The plan is authored once, before iteration 1; there is no per-iteration
  re-plan. On iterations 2-3, the verifier's findings route straight to the
  executor's `<task>` `<context>` (`code-executor.md:29-30`), where the
  executor authors the remediation.

**TRIVIAL/SMALL — the coordinator authors `plan.md` itself; zero
`acs:code-planner` spawns.** No Agent-tool spawn happens for this phase on
these lanes. The coordinator writes `<partition>/phases/code/plan.md`
directly, against the IDENTICAL artifact contract `code-planner.md` requires
— the same six required headings
(`## Spec analysis`, `## Executor tasks & file map`, `## Test strategy`,
`## Documentation map`, `## Risks`, `## Verifier checklist`), the same five
fold section literals in the exact order
`structure_lint.py --sections "Scope; Approach; API/data changes; Test plan; Out of scope" --ordered`
checks when the fold is active, the same two
mandatory verbatim clauses above, and an explicit statement of which intake
mode applied. **"Minimal" means the coordinator skips the separate-subagent
authorship step, never that a section is empty, a placeholder, or "see
ticket"** — every section must be substantive, because the verifier's
completeness sub-check (dimension 1) judges this artifact identically
whether the planner or the coordinator wrote it. This coordinator-authored
`plan.md` is passed to the executor's and the verifier's `<inputs>` exactly
like a planner-authored one — no downstream consumer sees a lesser artifact.

On TRIVIAL/SMALL the coordinator performs, at minimum: the AC-to-test
mapping, the executor file map, the test/coverage commands and tooling, the
`docs/product/prd.md`/`docs/product/roadmap.md` factual assessment (this
sub-check stays BLOCKING on every lane — skipping it only manufactures a
verifier finding), and the verifier checklist. The remaining
`code-planner.md` charter items — the Boy-scout drift survey, the E1-E4
doc-graph-gap check, the spec-simplicity gate, and the oversize signal — are
**best-effort** on these lanes only; their omission is never a finding.

**D-3 — mid-flight escalation never retro-spawns a planner.** When a
TRIVIAL/SMALL run escalates to STANDARD/COMPLEX mid-flight (see "In-loop
escalation check" above), the escalation raises verify depth and the
iteration ceiling only — it never spawns a planner after the fact, and the
coordinator-authored `plan.md` remains the plan artifact for the rest of the
run, because it already satisfies the same contract. The symmetric
user-confirmed de-escalation (see "Boundary-only user-confirmed
de-escalation" above) likewise never revokes an already-authored plan.

**D-4 — no plan XML message on the fast lanes.** Because no planner
subagent is spawned, no `<task phase="plan">` message is sent and no
`<result>` is returned — there is no plan message to validate and no
`iter-<n>-plan.xml` snapshot to persist on TRIVIAL/SMALL. `plan.md` remains
the durable record on every lane; the resume path is unchanged because it
keys on the presence of `plan.md`, never on who authored it.

### Plan approval (STANDARD/COMPLEX, after the plan, before the loop)

On STANDARD/COMPLEX lanes only — the same freshly recomputed lane as the
Plan step above — immediately after `plan.md` is written and before the
reflection loop begins, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/plan-approval.py" --ticket <ticket-id>
```

This script is the ONLY writer of `<partition>/phases/code/plan-approval.json`
— never a subagent's `Write` tool, and never the coordinator's own `Write`
either. An LLM-asserted approval is not an approval: eligibility is computed
by `acs_lib.plan_approval_eligible` from the plan artifact's own content plus
`settings.test_coverage_percent`, never by any agent's self-report.

The script writes at most one record per approved plan digest: a second
invocation over the same `plan.md` bytes is a no-op that re-asserts the
existing verdict (idempotent on resume, once per run otherwise); a revised
`plan.md` (a new sha256 digest) writes a fresh record. On TRIVIAL/SMALL the
script no-ops with `plan_approved: false` and writes no record at all — this
release does not extend approval to the fast lanes.

An ineligible plan does NOT block this release: the script exits 0, prints
the failing checks, and the coordinator continues the run with
`states.plan_approved: false`, at most revising `plan.md` once and
re-running the script before moving on — no loop, and nothing gates on
`plan_approved` in this release.

Copy the script's printed `plan_approved` value verbatim into
`<partition>/phases/code/result.json`'s `states.plan_approved` at Finish —
never assert it yourself.

An explicit `--plan` must resolve within `<partition>/phases/code/`; the
script rejects (clean stderr, exit 2, no record written) any `--plan` whose
realpath escapes that directory, and any future consumer of this record must
do the same rather than trust a caller-supplied path.

### Plan revocation

The escape hatch reached when a blocking `dimension="plan-conformance"`
finding's remedy is that the *plan* is wrong, not the changeset.

**Never automatic.** The trigger is reached only at an iteration or run
boundary — never mid-iteration — and only on an explicit user answer
recorded via `clarify.py add`, the same boundary-gated, confirmation-first
shape as `### Boundary-only user-confirmed de-escalation` above; letting the
loop dissolve its own contract without that confirmation is precisely the
rubber-stamp failure ADR 0004 exists to prevent.

1. **Copy before revise, never move.** `cp plan.md plan-superseded-<k>.md`,
   `<k>` the smallest positive integer with no existing file. The copy is
   byte-identical, so every `plan.md:<line>` citation already written into an
   earlier `iter-<n>-verify.md` resolves unchanged against
   `plan-superseded-<k>.md` — the operation is a copy, never a rename or
   move, and the superseded bytes are never deleted.
2. **Revise `plan.md` in place** (coordinator-authored; exactly one
   `code-planner` is spawned per run, so no planner re-spawn happens here —
   consistent with `### Plan approval`'s existing "at most revising `plan.md`
   once and re-running the script").
3. **Re-run `plan-approval.py --ticket <id>`.** The new digest writes a
   fresh record, so `plan-approval.json` always describes the *current*
   `plan.md`, and the superseded copies are the audit trail.
4. **`plan-superseded-<k>.md` is never an approval input and never a
   conformance contract** — guaranteed by dimension 15's activation
   condition that `plan_path` must equal `phases/code/plan.md`.

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

Send each executor a `<task phase="execute">` naming its spec file and its
file map (include `<constraint name="docs_only">true</constraint>` when it
applies). Each executor (artifact `<partition>/phases/code/iter-<n>-execute.json`,
or `iter-<n>-execute-<k>.json` when parallel) must, in order:

1. **Write failing tests first** for the spec's Test plan, run them, confirm
   they fail for the right reason. When the spec's Test plan names e2e flows
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
   `## Documentation map` names a doc section the code planner found already
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
diff (`git diff <default-branch>...HEAD`), all `<partition>/specs/*.md`,
`<partition>/ticket.json`, `<design.dir>/design.md` when it applies, and
`<partition>/phases/code/plan.md`. The verify `<task>`'s
`<constraints>` always carry `<constraint name="audience_style_profile">engineers
(implementation-contract prose)</constraint>` — the register the folded plan
content (or the plan's own analysis/decomposition prose) is judged against. The
verifier judges fresh — never forward executor reasoning — and RE-RUNS the
tests and coverage itself (artifact `<partition>/phases/code/iter-<n>-verify.md`).
Dimensions, each producing blocking findings on failure:

- **Acceptance-criteria conformance** — `ticket.json`'s `acceptance_criteria`/
  DoD re-read fresh every iteration, never the current plan artifact's
  restatement; the AC-to-implementation matrix is rebuilt from scratch each
  time. Carries the completeness (five mandatory sections substantive, no
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
  content when no separately-authored spec set exists.
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

**Split-answer termination (ADR 0069).** When `code-planner`'s plan artifact
carries the open oversize question, record the user's answer with
`clarify.py add`, the same as any other question above. On "accept one
large PR": continue planning against the current decomposition — nothing
else changes. On "split": the run ends in an orderly way — run the
mandatory Finish steps below first (so `post-code.py` closes the run entry
like any other terminal run), writing `<partition>/phases/code/result.json`
with `status: "failed"` and `stop_reason` "user chose to split; restructure
required before implementation", and only then return `<handoff
status="failed">` whose `<next-step>` reads `/acs:create-ticket split <id>
per <partition>/phases/code/plan.md` — it is the handoff element's
own `status` attribute, not only `result.json`'s field, that must read
`failed`. The `<summary>` (<=1 KB) must also restate the split instruction
in prose, not only `<next-step>`: under `/ship` the failed branch surfaces
`<summary>` verbatim and prints only generic resume commands, without
promising to surface `<next-step>`. No new XML element and no new status
value — `acs-messages.xsd` already admits `failed` and `<next-step>`.

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
       "plan_approved": true,
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

   **Four of these keys are DERIVED (MAR-523).** `verifier_passed`, `tests`,
   `pr` and `review.iterations` are **computed by the post-hook from the
   artifacts** — the verifier's verdict, the executors' execute reports, the
   forge, and the verify files on disk. Write your best value anyway (the
   document is a contract with humans too), but what lands is the computed one,
   and a disagreement is written to `runs[-1].derived_states.overrode` and
   printed. You cannot open the /acs:create-pr gate by writing `true`.

   Canonical `states` keys — EXACT names; pre-create-pr.py gates on them:
   - `verifier_passed`: **derived** from the verifier's `verdict.json` for the
     highest iteration (MAR-527); no passing verdict means `false`, whatever
     the document says. This is the /acs:create-pr gate.
   - `plan_approved`: `true`/`false`, copied verbatim from `plan-approval.py`'s
     printed output on STANDARD/COMPLEX (see `### Plan approval` above);
     `false` on TRIVIAL/SMALL or an ineligible plan. Not a gate this release.
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
     still open, 0 on success).

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
   iteration cap, needs input) in `stop_reason`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-code.py" --ticket <ticket-id> --result-file <partition>/phases/code/result.json
   ```

   If it exits non-zero, surface its stderr verbatim — the pipeline gate
   stays closed until it succeeds.

3. Report a compact summary to the user: branch, specs implemented,
   tests/coverage vs target, docs updated, review iterations and open
   findings, and the next step (`/acs:create-pr <ticket-id>` on success, or
   `/acs:create-ticket split <ticket-id> per
   <partition>/phases/code/plan.md` after a split answer).
   Under /acs:ship, instead return ONLY the `<handoff>` XML as your final
   message — status, summary (<=1KB), `<artifacts>` listing the branch and key
   changed paths, and `<next-step>` pointing at /acs:create-pr (or at
   `/acs:create-ticket split <ticket-id>` after a split answer).

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
- **Next**: `/acs:create-pr <ticket-id>` on success; on a coverage hard-fail or iteration cap, re-run `/acs:code <ticket-id>` after addressing the recorded findings
```

Any advisory documentation flags (`severity="info" dimension="documentation"`,
from code-verifier's demoted per-commit doc-sync, living-requirements, and
architectural-impact sub-checks) surface on the **Findings** line above
alongside open blocking findings and clarifications, or `none` when there
are none.

The non-epic COMPLEX breakdown recommendation (Start / escalation steps
above), when surfaced during this run, also appears on the **Findings**
line — a signal only in internal step-prose is not "surfaced" (D7-C).
