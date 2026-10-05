---
name: create-impl-plan
description: Turn an analyzed ticket — or requirements given as a prompt or documents — into the implementation plan /acs:code executes — the file-by-file approach, the declared executor file map, the test strategy its implementers run, and the spec fold. Writes plan.md to the change's Development folder, and it is also the artifact /acs:ship judges the delivery path from. Use after /acs:analyze-requirements and before /acs:code, which requires the plan. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[ticket-id] [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-impl-plan. Your job: turn ONE change's
requirements into the implementation plan `/acs:code` executes — the spec analysis, the
executor decomposition with its file map, the test strategy, the
documentation map, the risks, and the verifier checklist — published as
`plan.md` for the change, published to its Development folder. You orchestrate two subagents — a **planner** that decides the
slices, the file map and the test strategy and writes the plan draft, and a
**plan reviewer** that judges it fresh (planner → plan review, see the loop
below) — persist every phase artifact to the run partition, and finish by
writing the result document and running the post-hook — always, even on
failure.

You plan; you never implement. No production code, no tests, no repo docs
other than the plan artifact itself: `/acs:code` builds what this plan says.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-impl-plan --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround (`pre-create-impl-plan.py` checks only the safety
brakes: the run resolves to a live, unlocked partition and, when its subject
is a ticket, that ticket is not an epic — an epic is designed and fanned out,
never planned as one ticket. No ticket is required: a prompt, documents, or a
mix of them with a ticket id are all requirements. Nothing
upstream is required: `analysis.md` and `design.md` are read WHEN PRESENT, and
no predecessor-completed check exists — the pipeline order lives in
`workflows/ship.yaml`, not in this gate. With no analysis the plan is made
from the requirements' acceptance criteria and the codebase, whether `/acs:ship`
invoked this skill or a user did).

Parse the printed context JSON. Fields you will use:

- `requirements` — `{path, sources, acceptance_criteria, features, feature,
  needs_design}`. **Requirements: `context.requirements` / `acs.py requirements
  show` — a ticket id, documents and a prompt are only where they came from;
  never read ticket.json for acceptance criteria.** `requirements.path` is the
  run's `requirements.md` (a ticket's criteria numbered `AC-1…`, the prompt
  verbatim, the documents inlined or cited, and the `## Refined` section
  `/acs:analyze-requirements` wrote). The plan must satisfy every criterion in
  it.
- `ticket_id`, `ticket` — present only when a ticket is one of the sources:
  the tracker container (`type`, `size`, `stakes`, `docs_only`, `external`).
  Both are null on a prompt or document run.
- `partition` — absolute path of the run directory
  (`<workspace>/<repo-id>/runs/<run-id>/`). Phase artifacts go in
  `steps/create-impl-plan/`; the run ledger stays here too.
- `design` — `{required, dir, source}`. `design.dir` is the PARTITION of the
  ticket whose design applies (`source` is `"own"` or `"parent"` — child
  tickets plan against the parent epic's design); its basename is that
  ticket's id. When `design.required` is true, resolve the design document
  with `acs.py artifacts show --ticket <that id>` and read
  `artifacts["design.md"]` — the design record in
  `<architecture_dir>/lld/<feature>/<that id>/` (or a legacy
  `docs/tickets/<that id>/design.md`, read only), or `<design.dir>/design.md`
  when an older design still lives in the partition. On a ticketless run
  `design` is absent, or `{required, dir: null, source: "requirements"}` once
  analyze-requirements refined `needs_design`: read the run's own
  `artifacts["design.md"]` from `acs.py artifacts show` when it reports one. Call it `<design_doc>`; the plan is judged
  against it.
- `settings` — you need `tests.coverage` (the coverage target the plan
  states) and `tests.e2e` when set.
- `agents` — the agent name to spawn per role; the planner's and the plan
  reviewer's model and effort come from
  `settings.models.create-impl-plan.<role>` (inheriting when unset).
- `reconcile`, `handoff_summary`, `prior_status` — see
  `references/not-a-first-run.md`.

Throughout this file `<partition>` means the `partition` path from the context
JSON and `<id>` means `ticket_id` (e.g. `SHOP-123`) when the run has a ticket,
else `run_id`.

Locate the repo's documents once, here, the way any session finds them:
CLAUDE.md and whatever docs index it or the repo points at (e.g.
`docs/README.md`), then a Glob/Grep by file name or content. You need the
architecture doc set (its `hld/tech-stack.md`), the requirements set, the ADR
folder and the standards set. Record each one found as a repo-relative
directory and hand it to the subagents as a `<constraint>` of that name — the
planner takes `architecture_dir`, `requirements_dir` and `adr_dir`, the
plan reviewer `architecture_dir` and `standards_dir`. One the repo does not have is
simply absent: this skill creates none of them.

**Epics are refused by the gate** (a ticket-only check: a prompt or document
run has no type to refuse). Every ticket that reaches this step has
`ticket.type != "epic"`. If an epic reaches it anyway (a bypassed or
best-effort pre-gate on some runtime), STOP and surface the same message the
gate would have raised: design the epic with `/acs:create-design <id>`, fan it
out with `/acs:create-ticket <id>`, then run `/acs:create-impl-plan` on a
child.

## Working tree — the plan is a repo file

`plan.md` is a file in the consumer repo — the change's Development folder,
`<development_dir>/<feature>/<id>/` (ADR-0128) — unless run documents are kept
local (Share or keep local, below). This skill never creates, switches or names a branch,
and never stages, commits or pushes (ADR-0127): the published plan is left as
an uncommitted change in the working tree, on whatever is checked out, and its
path is recorded in the result's `states.files`. `/acs:create-pr` is the only
skill that branches and commits.

When `acs.py artifacts show` reports no path for `plan.md` (no checkout to
anchor the folder to, or no feature recorded for the run yet) the plan is
written to the workspace partition instead, and nothing enters the repo.

### Plan artifact resolution

`plan.md` is the change's implementation plan — ONE file per ticket (or per
ticketless run), one name, on every run. Resolve where it lives before
anything else:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show
```

It resolves by the run the checkout points at (`--run <run-id>` names
another; `--ticket <id>` still works). Development documents live in
`<development_dir>/<feature>/<id>/`, design records in
`<architecture_dir>/lld/<feature>/<id>/`, the feature's living analysis in
`<prd_dir>/features/<feature>/analysis.md` (`feature_analysis`); a legacy
`docs/tickets/<ID>/` file is reported only when the new folder has none, and
nothing writes there.

- `artifacts["plan.md"]` non-null → that existing file is the plan; this run
  REVISES it (see `references/not-a-first-run.md`). A legacy
  `docs/tickets/<ID>/plan.md` is revised by publishing the revision to
  `paths["plan.md"]`, never back into the legacy folder.
- else `paths["plan.md"]` non-null → the plan is published there.
- else → the plan is published to `<partition>/plan.md`.

This is exactly what `acs_lib.artifacts.artifact_path` resolves and what the
`/acs:code` gate looks for, so the path this run chooses is the path that
opens the next gate. Record it as `states.plan_path`.

One derived path follows from it:

- `steps/create-impl-plan/plan.md` — the working draft the planner writes,
  the plan reviewer judges, and every later reader reads.

**There is no approval mirror.** A byte-identical copy at `steps/code/plan.md`
used to exist because `plan-approval.py` hashed that path while the review
read another. One plan now (§6): the approval hashes the one file, and a copy
that can differ from its original is exactly the drift it was invented to
detect.

## The re-run reference, and when to open it

Nearly all of this skill is one flow: the planner surveys the ticket and
authors a plan draft, the plan reviewer judges it, you publish it. One part is not — what a run does when the ticket
already carries an interrupted prior run, or a published plan that has since
been superseded. It lives in a reference so a first run never reads it:

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/create-impl-plan/references/not-a-first-run.md` | `context.reconcile` or `context.handoff_summary` is set, OR a `plan.md` already exists for this ticket and this run is revising it (including the re-plan `/acs:ship` drives after `/acs:code` stops with `plan_superseded`). It carries the reconcile procedure and the plan-revocation escape hatch. |

## Inputs — gather before the loop

Read these yourself and name them by path in the planner's `<inputs>` (never
inline a file body):

1. The requirements — `requirements.path` from the context JSON (the run's
   `requirements.md`; the ticket, prompt and documents it was built from are
   only its containers).
2. `analysis.md` when `acs.py artifacts show` reports it — `/acs:analyze-requirements`'s
   impact map, assumptions, risks and refined acceptance criteria — and the
   feature's living analysis (`feature_analysis`, the Discovery analysis of the
   feature in `<prd_dir>/features/<feature>/analysis.md`) when it exists. Absent is
   not an error: plan from the requirements and the codebase instead, and say so in
   the plan.
3. `<design_doc>` when `design.required` — the decided architecture
   the plan must realize.
4. `<partition>/specs/*.md` when present (sorted `01-`, `02-`, ... — that is
   the dependency order). Absent or empty activates the spec authoring fold
   below.
5. The consumer repo: the source, tests and docs the change touches, plus the
   architecture doc set (`architecture_dir`) when the repo has one.

`api-contract.md` is NOT an input: `/acs:create-api-contract` runs AFTER this
skill and covers the API surface this plan declares.

## Reflection loop — planner → plan review

Two subagents, each named for what it does in this skill:

| Role | Agent | Kind | Spawn as | Writes |
|---|---|---|---|---|
| planner | `acs:create-impl-plan-planner` | write | `context.agents.planner` | `iter-<n>/authoring.md`, the draft `steps/create-impl-plan/plan.md`, `iter-<n>/planner.json` |
| plan reviewer | `acs:create-impl-plan-plan-reviewer` | judge | `context.agents.plan-reviewer` | `iter-<n>/plan-reviewer-<slice>.md`, one per judge slice, joined into `iter-<n>/plan-reviewer.md` |

The planner is a `write`-kind role — it produces the deliverable, a workspace
draft.

Run planner → plan review until the plan reviewer returns zero blocking
findings or the ceiling is reached. The planner is the only planning role:
iteration 1's planner surveys — spec intake, the
decomposition with its file map, the test strategy, the documentation map,
the risks, the verifier checklist — into its authoring notes and renders the
draft from them. The plan reviewer judges the draft fresh every iteration.

**One shape, on every run — and it could not be otherwise.** This skill runs
BEFORE the delivery path exists: `plan.md` is the artifact the path is judged
FROM, and its own `## Contract` block is where the judgement is recorded
(ADR-0095; the workflow's old `delivery:` block is gone). A plan skill that
branched on the path would be reading a decision its own output has not yet
been made to produce. So there is no fork here, and the ceiling is a fixed
**3** planner → plan-review rounds. Iteration 1's planner surveys before it
writes.

That symmetry is worth stating plainly: every ticket gets the same planning
rigor, and the plan is what earns a cheap or expensive implementation. Spending
less on a plan because someone guessed the work was small is exactly the
guess ADR-0095 removed.

**What an iteration counts:** one planner → plan-review round.

Decomposition is YOURS alone — subagents never spawn subagents.

### Parallelism — judge slices; the planner stays single

Every fan-out here is yours: spawn the N instances of the SAME agent in ONE
message (all foreground, in the same message), wait for all of them, and join
their outputs before the next phase. At most `settings.parallel.max_agents`
(default 4) instances run per message; beyond that, run the rest in waves of
that size.

**Writer — one planner, never sliced.** `plan.md` is a single document, so
the write is never partitioned. Its survey is not sliced either: the survey IS
the decomposition — one file map whose tasks must be disjoint from each
other, an AC-to-test matrix over every criterion — and that is one judgement
over the whole ticket that per-area slices could only produce in pieces that
collide. With one writer there is no integration pass, and with no survey
slices no synthesis of merged notes.

**Judge slices (every iteration — the default).** The plan reviewer has ten
check dimensions, so it always runs as three slices, each a fresh instance of
`acs:create-impl-plan-plan-reviewer` whose task carries `slice="<id>"` and
`<constraint name="dimensions">` naming the dimension numbers it owns:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `tests` | 1 acceptance-criteria coverage, 5 test strategy executability | the ONE run of the repo's existing suite command — the `suite` job you started beside the planner, read with `acs.py job wait --name suite` |
| `map` | 4 file-map honesty, 6 design and architecture conformance, 7 scope | the `git ls-files` / `ls` check of every mapped path |
| `document` | 2 completeness, 3 structure (fold only), 8 documentation map, 9 grounding, 10 authoring-conformance | `structure_lint.py` on the fold |

Grounding policing applies in every slice. Spawn the three slices in ONE
message; each writes `iter-<n>/plan-reviewer-<slice>.md`. Join them, in the
table's order, into the one report every later reader reads:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-impl-plan/iter-<n>/plan-reviewer.md \
  <partition>/steps/create-impl-plan/iter-<n>/plan-reviewer-tests.md \
  <partition>/steps/create-impl-plan/iter-<n>/plan-reviewer-map.md \
  <partition>/steps/create-impl-plan/iter-<n>/plan-reviewer-document.md
```

**De-duplicate after the join.** The slices own disjoint dimensions, so the
merge is the synthesis — but two slices can still report one defect (a mapped
path that does not exist is both a `file-map honesty` and a `grounding`
finding). Drop a finding that cites the same location and the same defect as
another slice's finding, keep the higher severity, and say so in the joined
report: append a `## De-duplicated findings` section to `iter-<n>/plan-reviewer.md`
listing each dropped finding (slice, dimension, location) and the finding it
duplicated (`_None._` when nothing was dropped). Never drop a finding for any
other reason.

**Pass rule for sliced judges:** the iteration passes only if EVERY slice
returned `status="completed"` with zero blocking findings. Any slice's
blocking finding blocks, and all slices' findings — de-duplicated as above,
otherwise verbatim — go to the next planner. A slice that failed or returned no usable result fails the
iteration — never "pass with a missing slice".

Messaging rules (`the SubagentStop hook's message check`):

- Send each subagent one `<task skill="create-impl-plan"
  phase="planner|plan-reviewer" ticket-id="<id>" iteration="n">` — the
  `phase` is the role — carrying `<objective>`, `<inputs>` (file refs) and
  `<constraints>`. The subagent returns a `<result>` with the same `phase` as
  its final content. A plan-reviewer slice's task and result also carry
  `slice="<id>"`; the un-sliced planner omits it.
- Validate EVERY message you send and receive — the SubagentStop hook checks each returned
  `<result>`'s `skill=`, `phase=` and `iteration=` (and `slice=` when sliced).

  On invalid: re-request once with the validation error; still invalid → fail
  the run and record the error in the result document's `errors`.
- Every phase output is persisted at the phase boundary, BEFORE the next
  phase starts: the SubagentStop hook snapshots each returned message to
  `steps/create-impl-plan/iter-<n>/<phase>-message.xml` (a slice's at
  `iter-<n>/<phase>-<slice>-message.xml`); if that snapshot is
  missing (a host that does not fire the hook), write the `<task>` and
  `<result>` there yourself. The roles' own reports are
  `iter-<n>/planner.json` and `iter-<n>/plan-reviewer-<slice>.md`, joined into
  `iter-<n>/plan-reviewer.md` — never write a message over them.
- Spawn subagents with the Agent tool: `subagent_type:
  "acs:create-impl-plan-planner"`, then `subagent_type:
  "acs:create-impl-plan-plan-reviewer"` — fall back to the un-namespaced name
  (`create-impl-plan-planner`, `create-impl-plan-plan-reviewer`) only if the
  runtime rejects the namespaced one. Spawn each role under the name in
  `context.agents.<role>` — the plugin's `acs:create-impl-plan-<role>`, or the
  generated `acs-create-impl-plan-<role>` copy `acs step start` wrote where
  `settings.models` sets a model or effort for it. Model and effort travel with
  that agent, so pass none of your own. If the runtime rejects the agent, FAIL
  the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

### The suite job — once per run, beside the planner

The `tests` slice's dimension 5 rests on one run of the repo's EXISTING suite
command, and that command does not depend on the plan. So you start it, as a
job (`${CLAUDE_PLUGIN_ROOT}/docs/INTERNALS.md`, "Jobs: commands beside the
agents"), in the same message as iteration 1's planner spawn:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" job start --name suite -- <the repo's existing suite command>
```

The command is the one the repo already documents (CLAUDE.md, the README, CI,
or `settings.tests` when it names one) — or, when the repo documents that run
as long, its `--collect-only`/`--help` equivalent, the plan reviewer's own
rule for dimension 5. Start it once per run, not per iteration: every
iteration's `tests` slice reads the same job with `acs.py job wait --name
suite` (it returns at once when the job has ended; on exit 3, still running,
it calls it again — never `sleep`) and never runs the suite itself. A repo
with no suite command starts no job, and you tell the `tests` slice so in its
`<constraints>`.

### Planner (per iteration) — survey, then author the plan

Iteration 1's planner surveys and decides before it writes the deliverable.
Task it with `<inputs>` of `requirements.md`, `analysis.md`, the feature's
living analysis and `design.md` when they exist, and the consumer-repo
source/docs the subject touches. Its authoring notes are
`steps/create-impl-plan/iter-<n>/authoring.md`, and they cover, in the order
`create-impl-plan-planner.md`'s survey defines:

- Analysis of the subject: implementation order, ambiguities and explicit
  clarifying questions (surface these — see User interaction — before the plan
  is published).
- The decomposition: typically ONE executor task per coherent slice, each
  listing the exact repo files it will touch (source, tests, docs) — this file
  map decides whether `/acs:code` may run its implementers in parallel, and it is
  what the PreToolUse write guard enforces.
- The test strategy per slice: which failing tests to write first, the repo's
  test/coverage tooling and the exact commands to run them, how
  `settings.tests.coverage` will be measured.
- The documentation map: whether any factual claims in `docs/product/prd.md`
  or `docs/product/roadmap.md` are made stale by the change (factual items:
  agent/subagent counts, shipped-vs-planned status, topology, version numbers,
  file path references) — `/acs:docs-sync` independently re-derives every
  other doc-delta (README/API/usage/changelog, the architecture doc set, ADRs)
  from the diff after `/acs:code` completes.
  The planner also performs a bounded, touched-area ADR-0012 doc-graph-gap
  check (`create-impl-plan-planner.md`'s survey item 4, edges E1-E4) — not the
  full shared design-time step `create-design`'s designer runs — riding the same
  `problems` carrier as the existing Boy-scout drift item.
- Risks, and what a reviewer should look hardest at.

**The plan is written for a human to approve in one read.** It works the way
Claude Code's own plan mode works, which is a deliberate borrowing of a shape
already proven and already familiar:

1. **Read-only until approved.** The survey investigates with read and search
   tools only. The planner writes exactly one file — the plan draft — and
   nothing else; no production code, no tests, no repo docs.
2. **Concrete steps against real paths**, the approach and the alternative
   rejected, and what is explicitly NOT being done. Prose and bullets, as
   short as the change allows.
3. **Approval is an explicit act and it is the gate** (see "Plan approval
   happens later, not here"). Feedback re-enters planning rather than leaking
   into implementation.
4. **Approval binds to the text that was approved** — `plan-approval.json`
   records `plan_sha256` over the approved bytes, so an edited plan is an
   unapproved plan.

**It is not a template.** There is no section-per-heading checklist to fill in
whether or not that heading has content: a `## Risks` heading with "none"
under it is worse than no heading, because it grades the document on its shape
rather than on what it says. Write what this change needs and stop.

**The machine-readable minimum.** "Not a template" is not "no structure":
three things downstream code reads must be findable without parsing prose, so
the plan ENDS with one section of fixed shape and everything above it is
free-form.

```markdown
## Contract
delivery_path: standard
owes:
  api_contract: true
  test_cases:   true
  e2e:          false
  reason: "CLI-only change; no HTTP surface, no browser flow"

### Executor tasks & file map
- task 1: plugins/acs/hooks/scripts/acs_lib/run.py, tests/acs/test_run_machine.py
- task 2: plugins/acs/skills/ship/SKILL.md
```

Three readers, three reasons:

- **`delivery_path`** — `trivial | small | standard | complex`, judged ONCE,
  here, from the plan's own scope (`skills/code/references/classify.md` is the
  rubric). `/acs:code` dispatches to its leg from it; nobody picks a path by
  hand and nothing re-judges it. Prefer the more expensive path whenever two
  fit: an unnecessary lens pass costs tokens, a missed regression in a
  load-bearing path costs more.
- **`owes`** — whether `/acs:create-api-contract`, `/acs:create-test-docs` and
  the e2e steps have work on this run. Each of those steps reads its own flag
  and records an evidenced no-op when the answer is false; **silence is not
  permission to skip**, so a step whose flag is absent does its work and
  decides for itself. `reason` is one sentence a reviewer can check.
- **the file map** — the executor partition, and the contract the file-map
  guard enforces on every Write. `### Executor tasks & file map` keeps its
  exact heading because the guard and `plan-approval.py` already key on it.

`plan_sha256` hashes the whole file, prose and contract alike, so editing
either invalidates the approval. A skill that needs a value reads the
`## Contract` block and nothing else; a human reads everything above it and
need not read the block at all.

**The plan IS the spec content.** There is no separate spec set and no
separate spec-authoring step: what a standalone create-spec planner would once
have written — the scope, the approach at contract level, the API and data
changes, the test plan, what is out of scope — is simply part of what the plan
says, in whatever shape this change needs. Two things that content must carry
wherever it lands: every `requirements.acceptance_criteria` entry maps to at least
one test the plan will write, and `settings.tests.coverage` is stated
explicitly. The approval predicate checks the second mechanically; the
plan reviewer checks the first.

**Oversize signal pointer.** `create-impl-plan-planner.md`'s survey item 2
compares this decomposition against the reviewable-diff bar; when it fires,
the split seams recorded above are what `/acs:create-ticket split` reads (see
User interaction for the split-answer termination).

**The draft.** Send the planner a `<task phase="planner">` naming the
resolved `plan_path` and (on iteration 2+) the iteration-1 authoring notes and
the plan reviewer's findings in `<context>`. The planner writes the plan draft to
`steps/create-impl-plan/plan.md` — one draft per run, revised in place across
iterations, never renumbered.

**Short is not empty.** A plan that says "see ticket", or a file map with no
files in it, fails the plan reviewer's completeness sub-check and the approval
predicate alike. What every plan carries, however short: the AC-to-test
mapping, the executor file map, the test and coverage commands, the
`docs/product/prd.md`/`docs/product/roadmap.md` factual assessment, and the
`## Contract` block. The remaining survey items — the Boy-scout drift survey,
the E1-E4 doc-graph-gap check, the simplicity gate and the oversize signal —
are best-effort; their omission is never a finding.

**Declare the file map** once the draft's `### Executor tasks & file map` is
settled — one call per task, additive (declaring task 2 never erases task 1),
with the exact paths that list names:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" filemap set \
  --skill code --iteration 1 --task <k> --file src/a.py --file tests/test_a.py
```

`--skill code` and `--iteration 1` are deliberate: the map this plan declares
is the map `/acs:code`'s first iteration of implementers is checked against, and
an undeclared map means no enforcement at all. `/acs:code` re-declares it for
its own remediation iterations. Record the returned `tasks` object as
`states.file_map`.

### Plan review (per iteration) — `acs:create-impl-plan-plan-reviewer`

Spawn the three `acs:create-impl-plan-plan-reviewer` slices (Judge slices
above) in ONE message AFTER the draft is written, each with
`<inputs>` of the draft, `requirements.md`, `analysis.md` and `design.md` when
they exist, every `<partition>/specs/*.md`, and the repo paths the file map
names; the `tests` slice's `<constraints>` also name the `suite` job (The
suite job, above) whose result it reads. The plan reviewer judges fresh — never forward the planner's reasoning —
and each slice writes `steps/create-impl-plan/iter-<n>/plan-reviewer-<slice>.md`,
which you join into `steps/create-impl-plan/iter-<n>/plan-reviewer.md`. The
slices' `<result>` `<findings>` are the verdict: `status="completed"` means
the review RAN, and an empty `<findings>` in every slice is the pass. Never
conclude a pass the plan reviewer did not report — a slice with no usable
result is no pass.

ALL blocking findings block — zero blocking findings = pass. On findings:
persist the review output, then AUTOMATICALLY re-run the planner, passing every
finding of every slice, verbatim once de-duplicated, to the next
iteration's planner in `<context>`. After the ceiling of
**3** planner → plan-review rounds with findings
remaining: stop with final status `"failed"`, the findings recorded, and
NOTHING published: on a first run `/acs:code`'s gate then stays shut because
the artifact it requires was never written, and on a re-plan the ticket keeps
the plan it already had rather than gaining an unverified one.

### Publish — the coordinator is the only writer of `plan.md`

Once the plan reviewer passes, publish the draft. **The coordinator performs
this step itself, never a subagent:** the file-map write guard
(`acs_lib/filemap.py`) denies any running `write`-kind agent — the planner
included — a write to a published plan, because the plan is precisely
the control input an implementer is checked against. Copy, never re-author —
the published bytes must equal the verified bytes:

```bash
draft="steps/create-impl-plan/plan.md"
mkdir -p "$(dirname "<plan_path>")" && cp "$draft" "<plan_path>"
```

Leave `<plan_path>` as an uncommitted change when it is inside the repo (the
Development folder) and record it in `states.files`; the run's own copy is
workspace state and never enters the repo.

### Share or keep local — asked once, in the same grouped ask (ADR-0132)

Whether `plan.md` enters the repo is a saved choice, not yours. Right after the
artifact resolution, before anything is written, ask acs:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs where --doc plan.md
```

- **`needs` empty** → follow it silently. `share: true` publishes to `path`,
  the phase folder; `share: false` keeps the document LOCAL — `path` is in the
  run's state folder (`steps/create-impl-plan/local/plan.md`), later steps
  still read it through `acs.py artifacts show`, it never enters
  `states.files`, and `/acs:create-pr` never commits it. Either way
  `<plan_path>` is its `abs_path`.
- **`needs` non-empty** → its questions join this skill's ONE grouped ask
  (User interaction), never a separate one; with no other question, ask them
  alone in one AskUserQuestion before Publish. `share`: "share run documents
  in the repo, or keep them local?" and "save this for you (this machine:
  `.acs/settings.local.json`) or for the team (`.acs/settings.json`)?".
  `location` (`location_source: default` — no setting, no existing folder):
  "use `proposed_path`, give another repo-relative folder, or keep documents
  local?" — keeping them local is the share answer, so ask its scope too. acs
  never creates a new docs folder without that answer. Record the answers in
  the ledger, then save them in ONE call carrying only what was answered — it
  prints the new `where`: `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs decide --share yes --scope team --location development=docs/development --doc plan.md`.
- **The user cannot be reached** (headless, nothing relayed in a `/acs:ship`
  brief) and `needs` is non-empty → keep the document LOCAL for this run only
  — `acs.py docs decide --share no --scope run`, nothing saved — and say so in
  the report.

The completion report names where it went: "shared to <path>", "kept local
(team default)", "kept local (your default)" or "kept local (this run only)".

### Plan approval happens later, not here

Approval binds on the `standard` and `complex` delivery paths only — and this
skill runs before any path exists, because `plan.md` is the artifact the path
is judged FROM. So `plan-approval.py` is not run here.

A human approves the plan with `plan-approval.py`, which is the **sole writer**
of `plan-approval.json` — never a coordinator, never a subagent, and never a
Write-tool call, because a record a skill can write itself is not an approval.
It hashes `steps/create-impl-plan/plan.md` into `plan_sha256`, and `/acs:code`'s
pre-hook refuses the deep paths when that digest does not match the plan on
disk. An edited plan is an unapproved plan.

What this skill owes approval is therefore one thing: **publish the plan and
leave it alone.**

### Docs-only tickets (`ticket.docs_only: true`, ticket runs only)

When the ticket carries the user-confirmed `docs_only` flag the plan changes
shape, not rigor: plan NO new tests and no coverage measurement — plan the
single full-suite run that proves the change breaks nothing, and state
`coverage_target: "n/a — docs_only"` in the test strategy. The file map lists
doc paths only. If the ticket cannot be delivered without touching executable
code or tests, the flag is wrong: surface that to the user (User interaction)
rather than planning around it.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list` (the run's
ledger — the ticket's when the run has one; `--ticket <id>` or `--run <run-id>`
names another)
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 of your own clarifications are open, present them in ONE grouped
interaction (a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips. Record each answer as its own `clarify.py add` entry (one
`C-<n>` per question, `--source` preserved). Never skip a question, merge two
questions into one entry, or auto-answer outside the existing
`--source assumption --rationale "..."` rule. Record every Q&A — obtained
interactively or relayed in a `/acs:ship` brief — with
`clarify.py add --skill create-impl-plan --question "..." --answer "..."`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`.

**Entries the analysis left open are proposals, not blockers.**
`analysis.md`'s front matter `ready_for_planning: true` is
`/acs:analyze-requirements`'s verdict that the ticket can be planned as written;
the ledger entries it recorded and left `open` alongside that verdict —
refined-criteria rewrites, missing-criterion suggestions, a design
recommendation — are for the user to take or leave, and that skill's own
contract is that with no answer this skill plans against the requirements as
written. So never re-ask them and never return `needs_input` for them: plan
against the requirements' acceptance criteria as written, name each such entry in
the plan's Risks section as `C-<n> open — planned as written`, and pass them
to the plan reviewer in `<context>` so the plan is judged against the requirements, not
the proposal. The 2026-09-14 measurement lost a run to the alternative: a
completed analysis with two open proposals, a plan run that asked instead of
planning, and no one to answer. What you ask about is what your own survey
finds genuinely ambiguous (next paragraph), the oversize question, and
nothing else.

When the requirements or a spec are genuinely ambiguous — it contradicts another
spec or the design, leaves behavior undefined, or admits several plausible
implementations with different user-visible outcomes — ask the user before
publishing. Do not guess on decisions that change behavior.

**Split-answer termination (ADR 0069).** When the planner's authoring notes carry
the open oversize question, record the user's answer with `clarify.py add`,
the same as any other question above. On "accept one large PR": continue
planning against the current decomposition — nothing else changes. On
"split": the run ends in an orderly way — run the mandatory Finish steps
below first (so `acs step finish` closes the run entry like any
other terminal run), writing
`steps/create-impl-plan/result.json` with `status: "failed"` and
`summary` "user chose to split; restructure required before
implementation", and only then return `<handoff status="failed">` whose
`<next-step>` reads `/acs:create-ticket split <id> per
steps/create-impl-plan/plan.md` — it is the handoff element's own
`status` attribute, not only `result.json`'s field, that must read `failed`.
The `<summary>` (≤1 KB) must also restate the split instruction in prose, not
only `<next-step>`: under `/acs:ship` the failed branch surfaces `<summary>`
verbatim and prints only generic resume commands, without promising to
surface `<next-step>`. No new XML element and no new status value —
the SubagentStop hook's message check already admits `failed` and `<next-step>`.

If you genuinely cannot reach the user (a non-interactive run): do not guess.
Record the outgoing questions as `open` (`clarify.py add` without `--answer`),
write the result document with `"status": "interrupted"` and
`"stop_reason": "needs_input"` (`needs_input` is a stop reason, not a status —
the post-hook refuses any status but `completed | failed | interrupted`), run
the Finish steps, and return a `<handoff status="needs_input">` whose
`<questions>` carry them.

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Leave any published plan in the working tree, flush
in-flight state plus soft context (user answers, decisions, which sections are
settled, gotchas) to
`steps/create-impl-plan/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/create-impl-plan/result.json` per the
   result-document contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "summary": "plan published and approved; 3 executor tasks, disjoint file maps",
     "states": {
       "plan_path": "docs/development/bulk-import/SHOP-123/plan.md",
       "plan_approved": false,
       "file_map": {"1": ["src/import/api.py", "tests/test_import_api.py"],
                    "2": ["docs/api/import.md"]},
       "files": ["docs/development/bulk-import/SHOP-123/plan.md"]
     },
     "findings": [],
     "errors": []
   }
   ```

   Canonical `states` keys — EXACT names; `acs step finish` documents
   them and the next steps read them:
   - `plan_path`: where `plan.md` was published (the Development folder, or
     the partition when there is no checkout or feature to anchor it to).
     `/acs:code`'s gate resolves the file itself; this records which path
     this run chose.
   - `plan_approved`: always `false` here. Approval is judged per delivery
     path, and the path does not exist yet when this skill runs — the
     `code-standard` and `code-complex` legs establish it at their own Start
     (ADR-0095). Recording `false` is the honest value, not a failure.
   - `file_map`: the declared executor file map as `acs.py filemap set`
     returned it (task id → repo paths), so a later run can see what scope the
     plan claimed.
   - `files`: every repo-relative path this run wrote and left uncommitted
     (the published `plan.md`; empty when the plan went to the partition or
     was kept local).
     `/acs:create-pr` commits them.

   On failure keep whatever is true: the `plan_path` only when a plan was
   actually published, `plan_approved: false`, the file map as far as it was
   declared, open findings in `findings`, and the reason (iteration cap,
   needs input, user chose to split) in `summary`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-impl-plan.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — the run is not closed
   until it succeeds.

3. Report a compact summary to the user: the published plan path (an
   uncommitted file in the working tree), the executor
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
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: plan path and where it went (shared / kept local, whose default); executor tasks and file-map disjointness; ACs mapped to tests; coverage target stated; the test strategy the code implementers will run
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <uncommitted files written (the plan path, repo-relative), partition phase artifacts>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:code <ticket-id>`; `/acs:create-api-contract <ticket-id>` first when the analysis declared an API surface change; after a split answer, `/acs:create-ticket split <ticket-id>`. The files stay uncommitted until `/acs:create-pr <ticket-id>`
```
