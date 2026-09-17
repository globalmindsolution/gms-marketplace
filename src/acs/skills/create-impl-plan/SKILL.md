---
name: create-impl-plan
description: Turn an analyzed ticket into the implementation plan /acs:code executes — the file-by-file approach, the declared executor file map, the test strategy its executors run, and the spec fold. Writes plan.md to the ticket's docs folder, and it is also the artifact /acs:ship judges the delivery path from. Use after /acs:analyze-ticket and before /acs:code, which requires the plan.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-impl-plan. Your job: turn ONE ticket
into the implementation plan `/acs:code` executes — the spec analysis, the
executor decomposition with its file map, the test strategy, the
documentation map, the risks, and the verifier checklist — published as
`plan.md` for the ticket, published to its docs folder and mirrored for an
approved plan. You orchestrate executor/verifier subagents — execute → verify,
no planner (ADR-0092) — persist
every phase artifact to the ticket partition, and finish by writing the
result document and running the post-hook — always, even on failure.

You plan; you never implement. No production code, no tests, no repo docs
other than the plan artifact itself: `/acs:code` builds what this plan says.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/skill-start.py" --skill create-impl-plan --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround (`pre-create-impl-plan.py` has verified the gate's
inputs: the ticket resolves to a live, unlocked partition and is not an epic —
an epic is designed and fanned out, never planned as one ticket. Nothing else
is required: `analysis.md` and `design.md` are read WHEN PRESENT, and no
predecessor-completed check exists — the pipeline order lives in
`workflows/ship.yaml`, not in this gate).

Parse the printed context JSON. Fields you will use:

- `ticket_id`, `ticket` — the resolved ticket (title, type, description,
  `acceptance_criteria`, `size`, `stakes`, `docs_only`, `external`). The plan
  must satisfy it.
- `partition` — absolute path of `<workspace>/<repo-id>/<ticket-id>/`. Phase
  artifacts go in `<partition>/phases/create-impl-plan/`; the run ledger stays
  here too.
- `design` — `{required, dir, source}`. `design.dir` is the PARTITION of the
  ticket whose design applies (`source` is `"own"` or `"parent"` — child
  tickets plan against the parent epic's design); its basename is that
  ticket's id. When `design.required` is true, resolve the design document
  with `acs.py artifacts show --ticket <that id>` and read
  `artifacts["design.md"]` — the design ticket's docs folder, or
  `<design.dir>/design.md` when the tree is opted out. Call it `<design_doc>`;
  the plan is judged against it.
- `settings` — you need `test_coverage_percent` (the coverage target the plan
  states), `architecture_path`, `requirements_path`, `adr_path`,
  `standards_path`, `artifacts.tickets_path` (where the plan is published),
  `formats.branch_name`, `formats.commit_message`, and `e2e` when set.
- `models` — per-role `{model, effort}` for executor/verifier.
- `reconcile`, `handoff_summary`, `prior_run_status` — see
  `references/not-a-first-run.md`.
- `post_hook` — absolute path to `post-create-impl-plan.py`.

Throughout this file `<partition>` means the `partition` path from the context
JSON and `<id>` means `ticket_id` (e.g. `SHOP-123`).

**Epics are refused by the gate.** Every ticket that reaches this step has
`ticket.type != "epic"`. If an epic reaches it anyway (a bypassed or
best-effort pre-gate on some runtime), STOP and surface the same message the
gate would have raised: design the epic with `/acs:create-design <id>`, fan it
out with `/acs:create-ticket <id>`, then run `/acs:create-impl-plan` on a
child.

## Branch — the plan is a repo file

When the ticket docs tree is active (`settings.artifacts.tickets_path` is not
null), `plan.md` is a file in the consumer repo and belongs on the ticket
branch with every other change for this ticket. Render
`settings.formats.branch_name` (default `"{type}/{ticket_id}-{slug}"`) with
`{ticket_id}`, `{type}` (`ticket.type`), `{slug}` (the slugified ticket title —
`acs.py slug --text "<title>"`), and `{external_key}`, then create or reuse it:

```bash
git rev-parse --verify --quiet "<branch>" && git checkout "<branch>" || git checkout -b "<branch>"
```

On resume the branch usually already exists — reuse it, never recreate or reset
it. Commit the published plan with `settings.formats.commit_message` (default
`"{ticket_id} {summary}"`). Do NOT push — `/acs:create-pr` pushes.

When the tree is opted out (`artifacts.tickets_path: null`) the plan is written
to the workspace partition instead, nothing enters the repo, and this step is a
no-op beyond staying on (or creating) the ticket branch for the skills that
follow.

### Plan artifact resolution

`plan.md` is the ticket's implementation plan — ONE file per ticket, one name,
on every run. Resolve where it lives before anything else:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show --ticket <id>
```

- `artifacts["plan.md"]` non-null → that existing file is the plan; this run
  REVISES it (see `references/not-a-first-run.md`).
- else `docs_dir` non-null → the plan is published to `<docs_dir>/plan.md`.
- else → the plan is published to `<partition>/plan.md`.

This is exactly what `acs_lib.artifacts.artifact_path` resolves and what the
`/acs:code` gate looks for, so the path this run chooses is the path that
opens the next gate. Record it as `states.plan_path`.

Two derived paths follow from it, and both are written from the SAME bytes:

- `<partition>/phases/create-impl-plan/plan.md` — the working draft the
  executor writes and the verifier judges (see Publish).
- `<partition>/phases/code/plan.md` — the approval mirror. `plan-approval.py`
  is the sole writer of the approval record and resolves the plan it hashes
  inside `<partition>/phases/code/`; `/acs:code`'s verifier reads that same
  path for its plan-conformance dimension. The mirror is a byte-identical copy
  of the published plan, never an independent edit.

## The re-run reference, and when to open it

Nearly all of this skill is one flow: survey the ticket, author a plan draft,
verify it, publish it. One part is not — what a run does when the ticket
already carries an interrupted prior run, or a published plan that has since
been superseded. It lives in a reference so a first run never reads it:

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/create-impl-plan/references/not-a-first-run.md` | `context.reconcile` or `context.handoff_summary` is set, OR a `plan.md` already exists for this ticket and this run is revising it (including the re-plan `/acs:ship` drives after `/acs:code` stops with `plan_superseded`). It carries the reconcile procedure and the plan-revocation escape hatch. |

## Inputs — gather before the loop

Read these yourself and name them by path in the executor's `<inputs>` (never
inline a file body):

1. The ticket — `ticket` from the context JSON (its file is whatever
   `acs.py artifacts show` reports as `source_path`).
2. `analysis.md` when `acs.py artifacts show` reports it — `/acs:analyze-ticket`'s
   impact map, assumptions, risks and refined acceptance criteria. Absent is
   not an error: plan from the ticket and the codebase instead, and say so in
   the plan.
3. `<design_doc>` when `design.required` — the decided architecture
   the plan must realize.
4. `<partition>/specs/*.md` when present (sorted `01-`, `02-`, ... — that is
   the dependency order). Absent or empty activates the spec authoring fold
   below.
5. The consumer repo: the source, tests and docs the change touches, plus the
   architecture doc set under `settings.architecture_path` when it exists.

`api-contract.md` is NOT an input: `/acs:create-api-contract` runs AFTER this
skill and covers the API surface this plan declares.

## Reflection loop — execute → verify, no planner

Run execute → verify until the verifier returns zero blocking findings or the
ceiling is reached. There is no plan phase: iteration 1's
executor surveys — spec intake, the decomposition with its file map, the test
strategy, the documentation map, the risks, the verifier checklist — into its
authoring notes and renders the draft from them. The verifier judges the draft
fresh every iteration.

**One shape, on every run — and it could not be otherwise.** This skill runs
BEFORE the delivery path exists: `plan.md` is the artifact /acs:ship judges the
path FROM (ADR-0095, `delivery.classify_after: create-impl-plan`). A plan skill
that branched on the path would be reading a decision its own output has not
yet been made to produce. So there is no fork here, and the ceiling is a fixed
**3** execute → verify rounds. Iteration 1's executor surveys before it writes.

That symmetry is worth stating plainly: every ticket gets the same planning
rigor, and the plan is what earns a cheap or expensive implementation. Spending
less on a plan because someone guessed the work was small is exactly the
guess ADR-0095 removed.

**What an iteration counts:** one execute → verify round.

Decomposition is YOURS alone — subagents never spawn subagents.

Messaging rules (`schemas/acs-messages.xsd`):

- Send each subagent one `<task skill="create-impl-plan"
  phase="execute|verify" ticket-id="<id>" iteration="n">` carrying
  `<objective>`, `<inputs>` (file refs) and `<constraints>`. The subagent
  returns a `<result>` as its final content.
- Validate EVERY message you send and receive:

  ```bash
  echo "<xml>" | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/validate_xml.py" -
  ```

  On invalid: re-request once with the validation error; still invalid → fail
  the run and record the error in the result document's `errors`.
- Persist every phase output to
  `<partition>/phases/create-impl-plan/iter-<n>-<phase>.xml` at the phase
  boundary, BEFORE starting the next phase.
- Spawn subagents with the Agent tool: `acs:create-impl-plan-executor` and
  `acs:create-impl-plan-verifier` —
  fall back to the un-namespaced name only if the runtime rejects the
  namespaced one. Apply `context.models.<role>.model` / `.effort` at spawn
  when not `"inherit"`; if the runtime rejects the model or effort, FAIL the
  run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

### Execute (per iteration) — survey, then author the plan draft

Iteration 1's executor surveys and decides before it
writes the deliverable. Task it with `<inputs>` of the ticket file,
`analysis.md` and `design.md` when they exist, every `<partition>/specs/*.md`,
and the consumer-repo source/docs the ticket touches. Its authoring notes are
`<partition>/phases/create-impl-plan/iter-<n>-authoring.md`, and they cover,
in the order `create-impl-plan-executor.md`'s survey defines:

- Analysis of the ticket and of every spec: implementation order (follow the
  spec numbering when specs exist), ambiguities and explicit clarifying
  questions (surface these — see User interaction — before the plan is
  published).
- The decomposition: typically ONE executor task per spec (or per coherent
  slice of the ticket when no specs exist), each listing the exact repo files
  it will touch (source, tests, docs) — this file map decides whether
  `/acs:code` may run its executors in parallel, and it is what the PreToolUse
  write guard enforces.
- The test strategy per slice: which failing tests to write first, the repo's
  test/coverage tooling and the exact commands to run them, how
  `settings.test_coverage_percent` will be measured.
- The documentation map: whether any factual claims in `docs/product/prd.md`
  or `docs/product/roadmap.md` are made stale by the change (factual items:
  agent/subagent counts, shipped-vs-planned status, topology, version numbers,
  file path references) — `/acs:docs-sync` independently re-derives every
  other doc-delta (README/API/usage/changelog, the architecture doc set, ADRs)
  from the diff after `/acs:code` completes.
  The executor also performs a bounded, touched-area ADR-0012 doc-graph-gap
  check (`create-impl-plan-executor.md`'s survey item 4, edges E1-E4) — not the
  full shared design-time step `create-design`'s executor runs — riding the same
  `problems` carrier as the existing Boy-scout drift item.
- Risks and the verifier checklist `/acs:code`'s verifier will run on top of
  its standing dimensions.

**Spec authoring fold (`specs/` absent or empty)**

Before producing the standard plan content, check whether
`<partition>/specs/` already has `.md` content.

When `<partition>/specs/` is empty or absent, the plan's author (the
`create-impl-plan-executor`) ADDITIONALLY produces, as part of the draft,
the spec content a standalone
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

**Oversize signal pointer.** `create-impl-plan-executor.md`'s survey item 2
also compares this decomposition against the reviewable-diff bar; when it
fires, the split seams recorded above are what `/acs:create-ticket split`
reads (see User interaction for the split-answer termination).

**Mandatory clauses** (both MUST appear verbatim in the plan artifact):

- "no separate /acs:create-spec invocation and no separate create-spec planner
  subagent" (AC-3)
- "every ticket.acceptance_criteria entry maps to at least one test the folded
  plan will write" (AC-4)

If specs already exist, the fold does NOT activate — the plan's author reads
the existing specs normally. The fold only activates when
`<partition>/specs/` is absent or empty.

**The draft.** Send the executor a `<task phase="execute">` naming the
resolved `plan_path` and (on iteration 2+) the iteration-1 authoring notes
and the verifier's findings in `<context>`. The executor writes the plan
draft to
`<partition>/phases/create-impl-plan/plan.md` — one draft per run, revised in
place across iterations, never renumbered — with EXACTLY these six top-level
headings, in this order:

`## Spec analysis`, `## Executor tasks & file map`, `## Test strategy`,
`## Documentation map`, `## Risks`, `## Verifier checklist`.

When the fold is active the draft additionally carries the five fold sections
in the exact order
`structure_lint.py --sections "Scope; Approach; API/data changes; Test plan; Out of scope" --ordered`
checks, plus the two mandatory verbatim clauses above and an explicit
statement of which intake mode applied (pre-existing specs, or folded).

**"Minimal" never means empty.** A section that is empty, a placeholder, or
"see ticket" fails the verifier's completeness sub-check. Every plan carries
the AC-to-test mapping, the executor file map, the test/coverage commands and
tooling, the `docs/product/prd.md`/`docs/product/roadmap.md` factual
assessment, and the verifier checklist — and the **Test strategy** section
earns its keep twice over now, because `/acs:code`'s executors take their
targeted test set from it and never re-derive one. The remaining survey items
— the Boy-scout drift survey, the E1-E4 doc-graph-gap check, the
spec-simplicity gate and the oversize signal — are best-effort; their omission
is never a finding.

**Declare the file map** once the draft's `## Executor tasks & file map` is
settled — one call per task, additive (declaring task 2 never erases task 1),
with the exact paths that table lists:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" filemap set \
  --skill code --iteration 1 --task <k> --file src/a.py --file tests/test_a.py
```

`--skill code` and `--iteration 1` are deliberate: the map this plan declares
is the map `/acs:code`'s first iteration of executors is checked against, and
an undeclared map means no enforcement at all. `/acs:code` re-declares it for
its own remediation iterations. Record the returned `tasks` object as
`states.file_map`.

### Verify (per iteration) — this IS the plan review

Spawn `acs:create-impl-plan-verifier` AFTER the draft is written, with
`<inputs>` of the draft, the ticket file, `analysis.md` and `design.md` when
they exist, every `<partition>/specs/*.md`, and the repo paths the file map
names. The verifier judges fresh — never forward the executor's reasoning —
and writes `<partition>/phases/create-impl-plan/iter-<n>-verify.md`. Its
`<result>`'s `<findings>` is the verdict: `status="completed"` means
verification RAN, and an empty `<findings>` is the pass. Never conclude a pass
the verifier did not report.

ALL blocking findings block — zero blocking findings = pass. On findings:
persist the verify output, then AUTOMATICALLY re-execute, passing every
finding to the next iteration's executor in `<context>` with no plan phase
in between. After the ceiling of **3** execute → verify rounds with findings
remaining: stop with final status `"failed"`, the findings recorded, and
NOTHING published: on a first run `/acs:code`'s gate then stays shut because
the artifact it requires was never written, and on a re-plan the ticket keeps
the plan it already had rather than gaining an unverified one.

### Publish — the coordinator is the only writer of `plan.md`

Once the verifier passes, publish the draft. **The coordinator performs this
step itself, never a subagent:** the file-map write guard
(`acs_lib/filemap.py`) denies any running executor a write under the ticket
docs tree, because the plan is precisely the control input an executor is
checked against. Copy, never re-author — the published bytes must equal the
verified bytes:

```bash
draft="<partition>/phases/create-impl-plan/plan.md"
mkdir -p "$(dirname "<plan_path>")" && cp "$draft" "<plan_path>"
mkdir -p "<partition>/phases/code" && cp "$draft" "<partition>/phases/code/plan.md"
```

Then commit `<plan_path>` on the ticket branch when it is inside the repo
(the docs tree active); the partition copy and the mirror are workspace state
and are never committed.

### Plan approval happens later, not here

Approval binds on the `standard` and `complex` delivery paths only — and this
skill runs before any path exists, because `plan.md` is the artifact the path
is judged FROM. So `plan-approval.py` is not run here. The `code-standard` and
`code-complex` legs run it at their own Start, over the approval mirror this
skill publishes at `<partition>/phases/code/plan.md`, which is exactly why
Publish writes that copy from the same bytes.

What this skill owes approval is therefore one thing: **publish the mirror from
the same bytes as the plan.** `plan_approval_eligible` hashes it, and a mirror
that differs from the published plan makes every later approval a verdict about
the wrong document.

### Docs-only tickets (`ticket.docs_only: true`)

When the ticket carries the user-confirmed `docs_only` flag the plan changes
shape, not rigor: plan NO new tests and no coverage measurement — plan the
single full-suite run that proves the change breaks nothing, and state
`coverage_target: "n/a — docs_only"` in the test strategy. The file map lists
doc paths only. If the ticket cannot be delivered without touching executable
code or tests, the flag is wrong: surface that to the user (User interaction)
rather than planning around it.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 of your own clarifications are open, present them in ONE grouped
interaction (a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips. Record each answer as its own `clarify.py add` entry (one
`C-<n>` per question, `--source` preserved). Never skip a question, merge two
questions into one entry, or auto-answer outside the existing
`--source assumption --rationale "..."` rule. Record every Q&A — obtained
interactively or relayed in a `/acs:ship` brief — with
`clarify.py add --skill create-impl-plan --question "..." --answer "..." --ticket <id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`.

**Entries the analysis left open are proposals, not blockers.**
`analysis.md`'s front matter `ready_for_planning: true` is
`/acs:analyze-ticket`'s verdict that the ticket can be planned as written;
the ledger entries it recorded and left `open` alongside that verdict —
refined-criteria rewrites, missing-criterion suggestions, a design
recommendation — are for the user to take or leave, and that skill's own
contract is that with no answer this skill plans against the ticket as
written. So never re-ask them and never return `needs_input` for them: plan
against the ticket's acceptance criteria as written, name each such entry in
the plan's Risks section as `C-<n> open — planned as written`, and pass them
to the verifier in `<context>` so the plan is judged against the ticket, not
the proposal. The 2026-09-14 measurement lost a run to the alternative: a
completed analysis with two open proposals, a plan run that asked instead of
planning, and no one to answer. What you ask about is what your own survey
finds genuinely ambiguous (next paragraph), the oversize question, and
nothing else.

When the ticket or a spec is genuinely ambiguous — it contradicts another
spec or the design, leaves behavior undefined, or admits several plausible
implementations with different user-visible outcomes — ask the user before
publishing. Do not guess on decisions that change behavior.

**Split-answer termination (ADR 0069).** When the executor's authoring notes carry
the open oversize question, record the user's answer with `clarify.py add`,
the same as any other question above. On "accept one large PR": continue
planning against the current decomposition — nothing else changes. On
"split": the run ends in an orderly way — run the mandatory Finish steps
below first (so `post-create-impl-plan.py` closes the run entry like any
other terminal run), writing
`<partition>/phases/create-impl-plan/result.json` with `status: "failed"` and
`stop_reason` "user chose to split; restructure required before
implementation", and only then return `<handoff status="failed">` whose
`<next-step>` reads `/acs:create-ticket split <id> per
<partition>/phases/create-impl-plan/plan.md` — it is the handoff element's own
`status` attribute, not only `result.json`'s field, that must read `failed`.
The `<summary>` (≤1 KB) must also restate the split instruction in prose, not
only `<next-step>`: under `/acs:ship` the failed branch surfaces `<summary>`
verbatim and prints only generic resume commands, without promising to
surface `<next-step>`. No new XML element and no new status value —
`acs-messages.xsd` already admits `failed` and `<next-step>`.

If you genuinely cannot reach the user (a non-interactive run): do not guess.
Record the outgoing questions as `open` (`clarify.py add` without `--answer`),
write the result document with status `"needs_input"` and `stop_reason`
"needs user input", run the Finish steps, and return a `<handoff
status="needs_input">` whose `<questions>` carry them. Validate it with
`validate_xml.py` like every other message.

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Commit any published plan on the branch, flush
in-flight state plus soft context (user answers, decisions, which sections are
settled, gotchas) to
`<partition>/phases/create-impl-plan/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `<partition>/phases/create-impl-plan/result.json` per the
   result-document contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "stop_reason": "plan published and approved; 3 executor tasks, disjoint file maps",
     "states": {
       "plan_path": "docs/tickets/SHOP-123/plan.md",
       "plan_approved": false,
       "file_map": {"1": ["src/import/api.py", "tests/test_import_api.py"],
                    "2": ["docs/api/import.md"]}
     },
     "findings": [],
     "errors": []
   }
   ```

   Canonical `states` keys — EXACT names; `post-create-impl-plan.py` documents
   them and the next steps read them:
   - `plan_path`: where `plan.md` was published (the ticket docs folder, or
     the partition when `artifacts.tickets_path` is null). `/acs:code`'s gate
     resolves the file itself; this records which path this run chose.
   - `plan_approved`: always `false` here. Approval is judged per delivery
     path, and the path does not exist yet when this skill runs — the
     `code-standard` and `code-complex` legs establish it at their own Start
     (ADR-0095). Recording `false` is the honest value, not a failure.
   - `file_map`: the declared executor file map as `acs.py filemap set`
     returned it (task id → repo paths), so a later run can see what scope the
     plan claimed.

   On failure keep whatever is true: the `plan_path` only when a plan was
   actually published, `plan_approved: false`, the file map as far as it was
   declared, open findings in `findings`, and the reason (iteration cap,
   needs input, user chose to split) in `stop_reason`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-impl-plan.py" --ticket <id> --result-file <partition>/phases/create-impl-plan/result.json
   ```

   If it exits non-zero, surface its stderr verbatim — the run is not closed
   until it succeeds.

3. Report a compact summary to the user: the published plan path, the executor
   tasks and whether their file maps are disjoint, the AC-to-test mapping
   count, approval, open findings, and the next step (`/acs:code <id>`, or
   `/acs:create-api-contract <id>` first when the analysis declared an API
   surface change, or `/acs:create-ticket split <id> per <plan path>` after a
   split answer). Under /acs:ship, instead return ONLY the `<handoff>` XML as
   your final message — status, summary (≤1 KB), `<artifacts>` listing the plan
   path, and `<next-step>` pointing at `/acs:code <ticket-id>` (or at
   `/acs:create-ticket split <ticket-id>` after a split answer).

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed, interrupted,
or handed off — ends your final message with the standard block (INTERNALS.md
"Completion report"), rendered only AFTER the post-hook succeeded. Same labels,
same order, `none` where empty; under `/acs:ship` your final message is the
`<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-impl-plan · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <stop_reason>
- **Results**: plan path; executor tasks and file-map disjointness; ACs mapped to tests; coverage target stated; the test strategy the code executors will run
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <plan path, partition phase artifacts, branch>
- **Metrics**: iterations <n>/<cap> · <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: `/acs:code <ticket-id>`; `/acs:create-api-contract <ticket-id>` first when the analysis declared an API surface change; after a split answer, `/acs:create-ticket split <ticket-id>`
```
