---
name: create-api-contract
description: Specify the API surface an approved plan adds or changes — every endpoint, command or message, its request/response shapes, error codes, compatibility notes and examples, each traced to an acceptance criterion and a plan item. Writes api-contract.md plus any machine-readable contract files the repo keeps. Use after /acs:create-impl-plan when the ticket's analysis found an API surface change. Use whenever a request asks to write down, spec out or document the shapes, flags, exit or error codes, or payloads of an interface a ticket's plan adds — REST, gRPC, CLI, webhook or event. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-api-contract. Your job: turn the API
surface the ticket's implementation plan declares into a specification others
can build and test against — `api-contract.md` for the ticket, plus the repo's
machine-readable contract files when it keeps any. Every item traces back to an
acceptance criterion AND to the plan item that introduces it. You orchestrate
two subagents over XML — the **contract-author** enumerates the surface and
writes the draft, the **contract-reviewer** re-derives the surface and judges
the draft fresh (contract-author → contract-reviewer); you never write the
contract content yourself. Both roles fan out in parallel where the work
splits: one contract-author per contract-file group when the surface spans
several, then one integration contract-author that reconciles the seams
between them (Writer slices), and the contract-reviewer's eight dimensions
across three reviewer slices on every review (Reviewer slices). Every fan-out
is yours — you spawn the slices in one message, have the seams synthesized,
and join their files with `acs.py notes merge`.

You specify; you never implement. No production code, no tests: `/acs:code`
implements this contract, `/acs:create-test-docs` derives contract cases from
it, and `/acs:review-code` checks the changeset against it.

This skill is independent: it runs the same whether `/acs:ship` invoked it or a
user did, and it never refuses because an earlier skill has not run. It works
from what it finds — the plan, the analysis, the design — and falls back to the
run's subject (the ticket's acceptance criteria, the prompt or the document)
when an upstream artifact is absent.

## When nothing is owed

`/acs:create-api-contract` is **not invoked at all** on a run that owes no
public surface. The plan's `## Contract` block records `owes.api_contract`,
and the pre-hook completes this step from it with
`outcome: no_surface_owed` — no coordinator, no subagents, zero tokens (§2.2).

That is an ANSWER on the ledger, not a step that silently did not run: a
reader sees `completed` with a reason, and `/acs:review-code`'s lens C reads
the same outcome and records that it had no contract to judge against.

Silence is not permission to skip. A plan that states nothing about
`owes.api_contract` does NOT settle the step — you run, and decide from the
plan and the subject whether a surface is owed.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-api-contract
```

If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
improvise a workaround. `pre-create-api-contract.py` refuses only what would do
damage re-running cannot undo: a ticket that does not resolve to a live,
unlocked partition, and an epic (an epic is designed and fanned out, never
given one contract). It never refuses because an upstream artifact is missing,
and there is no predecessor-completed check: order lives in
`workflows/ship.yaml`, not in this gate.

What you find decides how you scope the run, never whether it runs:

- `plan.md` present — **the primary input**; the contract covers exactly the
  surface this plan adds or changes.
- `plan.md` absent — work from the subject: the ticket's acceptance criteria
  (or the prompt / document) and the code are the scope. Say so in
  `## Scope & sources` and in the completion report, where the pointer is
  "run /acs:create-impl-plan <id> first" for a contract scoped by a plan.
- `analysis.md` present — its API-surface assessment (`api_surface`) and its
  evidence inform the survey. When it declares `api_surface: false` and you
  were invoked anyway, run: the contract-author's survey either finds the
  surface the analysis missed — report that disagreement — or finds none, and
  the run completes with `outcome: no_surface_owed`.
  Do not work around it by editing `analysis.md` yourself — the analysis is
  `/acs:analyze-requirements`'s artifact; a stale one is re-run there.
- `analysis.md` absent — the survey assesses the surface from the plan (or
  the subject) and the code alone.

Parse the printed context JSON. Fields you will use:

- `ticket_id`, `ticket` — the resolved ticket; its `acceptance_criteria` are
  what every contract item traces to.
- `partition` — absolute path of `<workspace>/<repo-id>/<ticket-id>/`. Phase
  artifacts go in `steps/create-api-contract/`.
- `checkout_root` — the consumer repo root.
- `design` — `{required, dir, source}`; `design.dir` is the PARTITION of the
  ticket whose design applies and its basename is that ticket's id. When
  `design.required`, resolve the design document with `acs.py artifacts show
  --ticket <that id>` (`artifacts["design.md"]` — its docs folder, or
  `<design.dir>/design.md` when an older design still lives in the partition)
  and read it for the interface decisions it already settled. Call it
  `<design_doc>`.
- `settings` — you need `formats.branch_name`, `formats.commit_message`.
- `models` — per-tier `{model, effort}`: the contract-author runs on the
  `executor` tier, the contract-reviewer on the `verifier` tier.
- `reconcile`, `handoff_summary`, `prior_status` — see Resume & reconcile.

Throughout this file `<partition>` means the `partition` path from the context
JSON and `<id>` means `ticket_id` (e.g. `SHOP-123`).

Locate the repo's architecture doc set (its `hld/tech-stack.md`; its
`lld/contracts.md` is the existing contract narrative) once, here, the way any
session finds a document: CLAUDE.md and whatever docs index it or the repo
points at (e.g. `docs/README.md`), then a Glob/Grep by file name or content.
Its repo-relative directory is `<architecture_dir>` below. A repo without one
simply has none; this skill does not create it.

## Branch — the contract is a repo file

`api-contract.md` (in the ticket's docs folder, `docs/tickets/<id>/`) and
every machine-readable contract file belong on the ticket branch with the rest
of the change. Render `settings.formats.branch_name` (default
`"{type}/{ticket_id}-{slug}"`) with `{ticket_id}`, `{type}` (`ticket.type`),
`{slug}` (`acs.py slug --text "<title>"`) and `{external_key}`, then create or
reuse it:

```bash
git rev-parse --verify --quiet "<branch>" && git checkout "<branch>" || git checkout -b "<branch>"
```

The branch normally already exists — `/acs:analyze-requirements` and
`/acs:create-impl-plan` ran before this step. Reuse it; never recreate or reset
it. Commit with `settings.formats.commit_message` (default
`"{ticket_id} {summary}"`). Do NOT push — `/acs:create-pr` pushes.

### Contract artifact resolution

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show --ticket <id>
```

- `artifacts["api-contract.md"]` non-null → that existing file is the contract;
  this run REVISES it in place (a superseded plan, a review finding, a second
  surface). One contract per ticket, one name.
- else `docs_dir` non-null → publish to `<docs_dir>/api-contract.md`.
- else → publish to `<partition>/api-contract.md`.

Call it `<contract_path>`; record it as `states.contract_path`. The same call
reports `artifacts["plan.md"]` and `artifacts["analysis.md"]` — the exact paths
the gate resolved (`null` when one does not exist). Pass THOSE paths to every
subagent `<inputs>`; do not
re-derive them.

The working draft lives at
`steps/create-api-contract/api-contract.md`; the published file is
a copy of those exact bytes (see Publish).

### Machine-readable contract files

The repo's machine-readable contracts — an OpenAPI document, JSON Schemas,
`.proto` files, a GraphQL SDL, a CLI reference generated from the parser,
whatever this repo already uses — live where the repo keeps them, else at
`docs/api/`, the conventional default. Locate them the way any session finds a
document: CLAUDE.md and whatever docs index it or the repo points at (e.g.
`docs/README.md`), then a Glob/Grep by file name or content, and `docs/api/`.
Resolve the mode ONCE, before the first subagent is spawned, and state it in
every task's `<constraints>`:

- none found → mode `no-machine-readable-contracts`. Do NOT invent the
  convention: record that in `## Contract files` and leave the tree absent.
  Introducing a contract format a repo has never used is an architecture
  decision, not this skill's call — raise it as a question if it matters; a
  format the user adopts goes in `docs/api/`.
- found → mode is the repo-relative directory that holds them
  (`<contracts_dir>`). Identify the files that describe the touched surface (by
  reading them, not by guessing filenames) and update them as part of this run,
  in the format they already use.

Those two token values are what `<constraint name="contracts_mode">` carries
into every phase, so the contract-author and the contract-reviewer work against
the same resolution. The same resolution decides whether the contract-authors
run sliced (see Writer slices): decide that here too, once, before the first
spawn.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality BEFORE
continuing:

1. Read `steps/create-api-contract/state.json` (`invocations[-1]`, `states`) and
   the artifacts under `steps/create-api-contract/`.
2. Re-resolve `<contract_path>` and read it if it exists; check `git status` /
   `git log` for contract-file changes a prior run committed. Trust nothing you
   cannot see in a file or a commit.
3. Continue from the first unfinished phase — a contract-author report
   (`iter-<n>/contract-author.json`) with no contract-reviewer report →
   review it; a contract-reviewer report (`iter-<n>/contract-reviewer.md`)
   with findings and no later contract-author → re-run the contract-author
   with those findings as `<context>`; nothing on disk → iteration 1
   contract-author.
4. The contract-author's authoring notes (`iter-<n>/authoring.md`) belong to
   their iteration, and a resumed run never re-runs an iteration whose
   contract-reviewer report is already on disk.
5. A sliced phase resumes slice by slice: a resumed iteration re-runs ONLY the
   slices whose report is missing — a writer slice without
   `iter-<n>/contract-author-<k>.json`, a reviewer slice without
   `iter-<n>/contract-reviewer-<slice>.md` — spawned together in one message,
   then runs the join. Every writer slice's report on disk but no
   `iter-<n>/contract-author-integration.json` → run the integration pass, then
   the join. Every report on disk but no joined file (`iter-<n>/authoring.md`
   and the draft, or `iter-<n>/contract-reviewer.md`) → run the join alone;
   never re-run a slice whose report is on disk.

If `context.handoff_summary` exists, read it plus
`steps/create-api-contract/handoff-context.md` (when present), do
a light reconcile, and continue from where it points.

## Inputs — gather before the loop

Name these by path in the contract-author's `<inputs>` (never inline a file
body); an input that does not exist is named as absent, never invented:

1. `plan.md` (the path `artifacts show` reported), when it exists — **the
   primary input**. The contract covers the surface THIS plan adds or changes:
   its executor tasks, file map and API/data-changes content are the scope
   boundary. A surface the plan does not touch is out of scope, however
   tempting. With no plan, the ticket's acceptance criteria are the boundary.
2. `analysis.md`, when it exists — the API-surface assessment and its
   evidence, the impact map, the assumptions and the refined acceptance
   criteria.
3. The ticket document (`source_path` from `artifacts show`) — the acceptance
   criteria every item traces to.
4. `<design_doc>` when `design.required` — interface decisions the
   design already settled are binding; the contract renders them, never
   re-opens them.
5. The architecture doc set when it exists: `<architecture_dir>/lld/contracts.md`
   and the `lld/flows/` diagrams for the touched flows.
6. The existing contract files under `<checkout_root>/<contracts_dir>/` when
   the repo keeps them, plus the code that implements today's surface (the
   handler, the parser, the emitter) — the current shape is what "changed" is
   measured against.

## Reflection loop — contract-author → contract-reviewer

Run contract-author → contract-reviewer until the contract-reviewer returns
zero blocking findings or the cap is reached. The cap is a
fixed **3** on every run — `/acs:create-api-contract` has
no path-driven verify depth. Iteration 1's
contract-author surveys the inputs, writes its authoring notes, and authors the
contract draft from them; the contract-reviewer re-derives the surface and
judges the result fresh. On iterations 2-3 the contract-reviewer's findings go
verbatim into the next contract-author `<task>` `<context>` and the
contract-author authors the remediation.

**What an iteration counts:** one contract-author → contract-reviewer round.

Decomposition is YOURS alone — subagents never spawn subagents, so every
parallel fan-out below is yours to spawn and yours to join.

Messaging rules (`the SubagentStop hook's message check`):

- Send each subagent one `<task skill="create-api-contract"
  phase="contract-author|contract-reviewer" ticket-id="<id>" iteration="n">` with
  `<objective>`, `<inputs>` (file refs) and `<constraints>` — always
  `required_sections` (the seven headings below), `audience_style_profile`
  (`integrators (precise shapes + examples)`), and `contracts_mode` (the mode
  resolved above).
- A sliced instance's task carries its slice id,
  `<task skill="create-api-contract" phase="contract-reviewer" slice="trace" …>`,
  and its `<result … slice="trace" …>` echoes it, so the SubagentStop snapshot
  lands at `iter-<n>/<phase>-<slice>-message.xml` and parallel results never
  overwrite each other. A single, un-sliced instance omits `slice`.
- Validate EVERY message you send and receive — the SubagentStop hook checks
  each returned `<result>`'s `skill=`, `phase=` and `iteration=`. On invalid:
  re-request once with the validation error quoted; still invalid → fail the
  run and record the error in the result document's `errors`.
- Every phase output is persisted at the phase boundary, BEFORE the next phase
  starts: the SubagentStop hook snapshots each returned message to
  `steps/create-api-contract/iter-<n>/<phase>-message.xml` (`<phase>` is the
  role); if that snapshot is missing (a host that does not fire the hook),
  write the `<task>` and `<result>` there yourself.
- Spawn subagents with the Agent tool: `subagent_type:
  "acs:create-api-contract-contract-author"` and
  `"acs:create-api-contract-contract-reviewer"` — fall back to the
  un-namespaced name (`create-api-contract-contract-author`,
  `create-api-contract-contract-reviewer`) only if the runtime rejects the
  namespaced one. Apply `context.models.<tier>.model` / `.effort` at spawn when
  not `"inherit"` — tier `executor` for the contract-author, `verifier` for the
  contract-reviewer; if the runtime rejects the model or effort, FAIL the run
  with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

### Phase: contract-author — `acs:create-api-contract-contract-author`

Objective, iteration 1: enumerate the surface. From the plan, the analysis,
the design and the code (or, with no plan, the subject and the code), record in
the authoring notes
(`steps/create-api-contract/iter-<n>/authoring.md`) one entry per
endpoint/command/message/schema/signature the plan adds or changes — each
with its kind, its current shape (or "new"), the plan item and acceptance
criterion it traces to, the compatibility question it raises, and which
machine-readable contract file (when the tree exists) describes it — plus the
genuinely open questions (a versioning or breaking-change decision the plan
does not settle is exactly such a question). Then write the contract draft
from those notes. The notes are what the contract-reviewer checks the draft
against.

If the contract-author returns `needs_input` with `<questions>`, resolve them
in User interaction and re-run the contract-author for the same iteration with
the answers in `<context>`.

If the survey finds no surface at all — nothing the plan or the subject adds or
changes is an endpoint, command, message, schema, signature or persisted
format — the contract-author says so in its report (`items: 0`) and writes no
draft. Skip the contract-reviewer, publish nothing, and complete with
`outcome: no_surface_owed` and the survey's reason in `summary`.

The same phase then writes the contract draft to
`steps/create-api-contract/api-contract.md` — one draft per run,
revised in place across iterations — and, when the mode says the repo keeps
machine-readable contracts, update those files in the consumer repo and commit
them on the ticket branch. When the contract-authors run sliced (Writer
slices, below), each slice does all of this for its own group only, and you
assemble the one draft from their fragments.

The draft's front matter and its seven headings, in this order:

```markdown
---
ticket: SHOP-123
items: 3
contract_files: ["docs/api/openapi.yaml"]
---

# API contract — SHOP-123: Accept CSV imports over 10 MB

## Scope & sources
## Surface
## Error model
## Compatibility & versioning
## Examples
## Traceability
## Contract files
```

`## Surface` carries one `### ` subsection per item — what each holds is
defined in `create-api-contract-contract-author.md`. `items` in the front matter is
the number of those subsections, and `contract_files` is the repo-relative list
of machine-readable files this run changed (`[]` when none).

On iteration ≥ 2 the contract-author fixes every finding in `<context>` and
nothing else.

#### Writer slices — one contract-author per contract-file group

When the contract splits into disjoint files, the contract-authors run in
parallel from iteration 1 — that is the default, not an optimisation to reach
for. Decide it once, after `contracts_mode` is resolved and before the first
spawn:

- **When.** `plan.md` exists, `contracts_mode` is a real `<contracts_dir>`, and
  the plan's file map (or its API/data-changes content) touches two or more
  contract-file groups. Otherwise — `no-machine-readable-contracts`, no plan,
  or a single group — ONE contract-author writes the whole draft, un-sliced:
  the contract is then a single document with nothing disjoint to hand out.
- **The partition rule.** A group is a set of machine-readable contract files
  under `<contracts_dir>` that describe one API: files that reference one
  another (a `$ref`, an `import`, an `include`) or that describe the same item
  are ONE group. Establish the groups by reading the files the plan names,
  never from their names; when you cannot establish them, do not slice. One
  slice owns one group — its contract files (only that slice edits and commits
  them), the surface items those files describe, and its own fragment of the
  draft — and the FIRST slice also owns every item no contract file describes
  (a CLI flag, a library signature). Every contract file is in exactly one
  group and every item has exactly one owner: that is the guarantee two slices
  cannot overlap. Each task names its own group's files AND every other
  group's in `<constraint name="slice_scope">`, so a slice knows what it must
  not touch.
- **Slice ids.** The group's primary file stem, lowercase (`openapi`,
  `events`, `billing-api`) — `acs.py notes merge` reads a slice id as what
  follows the prefix its inputs share, so a hyphen is fine. `preamble` and
  `integration` are reserved.
- **What a slice writes.** Its notes `iter-<n>/authoring-<k>.md`; its fragment
  `steps/create-api-contract/api-contract-<k>.md` — the seven headings in
  order, no front matter and no title, only its own items, revised in place
  across iterations; its report `iter-<n>/contract-author-<k>.json`; and its
  group's contract files.
- **One message.** Spawn every slice of a wave in ONE message — one Agent call
  per slice, all in the same assistant message, in the foreground — then wait
  for ALL of them before anything else happens. At most `max_parallel = 4`
  slices per message; more groups run in waves of at most four, the next wave
  spawned only once every slice of the previous one returned.
- **One branch, one working tree.** Each slice stages and commits ONLY its own
  group's files, by name (`git commit -m "<msg>" -- <its files>`) — never
  `git add -A` or `git commit -a`, which would sweep up a sibling's work in
  flight — and on `index.lock` contention it waits briefly and retries the
  commit. Nothing is ever forced.
- **Questions and failures.** The `<questions>` of every slice that returned
  `needs_input` go to the user in ONE grouped ask (User interaction); then only
  those slices re-run, under the same id, with the answers in `<context>`. A
  slice that `failed` is re-run alone once; still failed → the run fails. The
  join waits until every slice of the iteration has `completed`.
- **The integration pass — synthesis, before the join and before the
  reviewer.** A mechanical join is not a synthesis: slices that each wrote
  their own group can disagree where the groups meet. Once every slice has
  completed, spawn ONE more contract-author with `slice="integration"` (the
  pattern `/acs:code-complex`'s final integration implementer uses). Its
  `<inputs>` name every slice's fragment, latest notes, latest report and
  contract files. It reconciles ONLY the seams between groups, and edits the
  fragments and contract files in place to do it:
  - **error codes** — a code two groups return carries one meaning, one
    wording and one status across every fragment's `## Error model` table;
  - **shared definitions** — a type, enum, field name or identifier two
    groups both use (a shared error body, a status enum, an id format) is
    spelled and shaped the same in every fragment and every contract file;
  - **cross-references** — an item in one group that names an item in
    another (an endpoint that emits a message, a command that prints a
    schema) names it exactly as the owning fragment's `### ` heading does;
  - **compatibility decisions** — two slices citing the same `C-n` state the
    same verdict and decision;
  - **scope and traceability hand-offs** — a surface one slice excluded as
    "another group's" is specified by that group (nothing dropped between
    slices), and an acceptance criterion one slice marks as a gap is not
    covered by another slice's item;
  - **indexes** — any index or README under `<contracts_dir>` that lists the
    contract files names every group's files.

  It never rewrites a slice's substance and never adds or removes an item —
  the derived `items` count stays true. Where the slices' notes contradict
  each other, it records the resolution with its evidence under a
  `## Synthesis` heading in its own notes, `iter-<n>/authoring-integration.md`,
  never silently picking one; a genuine conflict it cannot resolve from the
  evidence comes back as `status="needs_input"` with the question. It writes
  `iter-<n>/contract-author-integration.json` listing each seam it changed
  (file, what, why, which slices), and commits any contract file it touched
  by name, retrying on `index.lock` contention like every slice. The pass is
  skipped only when the contract-author ran un-sliced — one writer has no
  seams.
- **The join — deterministic, never by hand.** Once the integration pass
  completed:
  1. Join the notes — each slice's LATEST notes (this iteration's when it ran,
     else those of the iteration it last ran), in slice order, and the
     integration pass's notes last:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
       --out <partition>/steps/create-api-contract/iter-<n>/authoring.md \
       <partition>/steps/create-api-contract/iter-<n>/authoring-<k1>.md <…/authoring-<k2>.md> … \
       <partition>/steps/create-api-contract/iter-<n>/authoring-integration.md
     ```

  2. Write `steps/create-api-contract/api-contract-preamble.md`: the front
     matter and the `# API contract — <id>: <title>` line, nothing else, every
     value DERIVED — `ticket` is `<id>`, `items` the sum of the slices' latest
     reports' `items`, `contract_files` the union of their `contract_files`.
     It is the one draft file you write, and it holds no contract content.
  3. Join the draft, the preamble first and then the fragments of every slice
     with `items` > 0, in slice order:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge --no-markers \
       --out <partition>/steps/create-api-contract/api-contract.md \
       <partition>/steps/create-api-contract/api-contract-preamble.md \
       <partition>/steps/create-api-contract/api-contract-<k1>.md <…/api-contract-<k2>.md> …
     ```

  The merge keeps the first input's preamble — the derived front matter — and
  lays each fragment's body under the one heading they share; `--no-markers`
  leaves out the `<!-- slice: … -->` lines, because this draft is what Publish
  copies into the repo (the notes and reviewer-report joins keep them — they
  stay in the workspace), so the
  contract-reviewer, the deterministic checks and Publish all read ONE draft
  with each of the seven headings once. A slice whose report miscounts its
  items is caught there: the reviewer's `front-matter` dimension checks the
  derived `items` against the `### ` subsections.
- **Iteration 2+.** Group the findings by the slice that owns the item or
  contract file each one names, and re-run only those slices — each with
  EVERY finding verbatim in its `<context>`, fixing the ones in its own group.
  A seam finding — one that spans two groups, or names an inconsistency
  between fragments — goes to the next iteration's integration pass, not to
  the slices. A slice not re-run keeps its fragment, notes and report as they
  are. The integration pass then runs again, with every finding in its
  `<context>` (alone, when only seam findings were open), and the join
  follows.
- **No surface.** Every slice reporting `items: 0` completes the run with
  `outcome: no_surface_owed`, exactly as un-sliced. A slice with `items: 0`
  writes no fragment and is left out of the draft join; its notes still join.

### Phase: contract-reviewer — `acs:create-api-contract-contract-reviewer`

Spawn `acs:create-api-contract-contract-reviewer` AFTER the draft is written,
with `<inputs>` of the draft, the authoring notes (`iter-<n>/authoring.md`),
the contract-author report (`iter-<n>/contract-author.json`), `plan.md` and
`analysis.md` when they exist, the ticket document, `design.md` when it binds,
and every contract file the contract-author touched. It judges fresh — never
forward the contract-author's reasoning — re-derives the surface from the plan
(or the subject) and the code itself, and writes
`steps/create-api-contract/iter-<n>/contract-reviewer.md`. When the
contract-authors ran sliced, `<inputs>` name every slice's latest report
(`iter-<n>/contract-author-<k>.json`), the integration pass's
`iter-<n>/contract-author-integration.json` and every group's contract files,
beside the joined draft and the joined notes — the reviewer judges the
integrated result, and a seam inconsistency it finds is a finding for the next
iteration's integration pass.

#### Reviewer slices — the eight dimensions in three parallel judges

The contract-reviewer has eight check dimensions, so every review runs as
three fresh instances of the SAME agent, one per slice, each told its
dimensions in `<constraint name="dimensions">`:

| slice | dimensions | owns the check |
| --- | --- | --- |
| `surface` | 1 `completeness`, 2 `accuracy`, 7 `scope` | re-deriving the surface from the plan (or the subject) and the code |
| `trace` | 3 `traceability`, 4 `compatibility`, 8 `authoring-conformance` | `clarify.py list` against the ledger |
| `files` | 5 `contract-files`, 6 `front-matter` and `structure` | `front_matter_check.py`, `structure_lint.py`, `git log` / `git show` of the contract files |

Spawn the three in ONE message — one Agent call per slice, all in the same
assistant message, in the foreground (three is within `max_parallel = 4`) —
and wait for ALL of them. Each writes
`iter-<n>/contract-reviewer-<slice>.md`; join them, in the table's order, into
the one report every reader expects:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-api-contract/iter-<n>/contract-reviewer.md \
  <partition>/steps/create-api-contract/iter-<n>/contract-reviewer-surface.md \
  <partition>/steps/create-api-contract/iter-<n>/contract-reviewer-trace.md \
  <partition>/steps/create-api-contract/iter-<n>/contract-reviewer-files.md
```

**De-duplication — the join is the synthesis.** The slices own disjoint
dimensions, so the merge is the synthesis; you additionally drop a finding
that cites the same location and the same defect as another slice's finding,
keeping the one with the higher severity, and say so in the joined report:
append a `## De-duplicated findings` section to
`iter-<n>/contract-reviewer.md` naming each dropped finding, its slice, and
the kept finding it duplicates. Two findings on the same location for
different defects are both kept.

**The pass rule for sliced reviewers.** The iteration passes only if EVERY
slice returned `status="completed"` with zero blocking findings. Any slice's
blocking finding blocks, and all three slices' findings — de-duplicated,
otherwise verbatim — go to the next contract-author. A slice that returned
`status="failed"` or no usable `<result>` (after the one re-request) fails
the iteration exactly as a blocking finding does —
never "pass with a missing slice".

ALL blocking findings block — zero blocking findings = pass.
`status="completed"` means the review RAN; the empty `<findings>` is the
pass. On findings: persist, then AUTOMATICALLY re-run the contract-author with
every finding in its `<context>`. After iteration 3 with findings remaining:
stop with final status `"failed"`, findings recorded, and no published
contract — `/acs:code` then implements against the plan alone, which is exactly
the ambiguity this step exists to remove, so say so in `summary`.

### Deterministic checks the coordinator runs before publishing

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/front_matter_check.py" \
  --require "ticket: str; items: int; contract_files: list" \
  --ticket <id> "steps/create-api-contract/api-contract.md"

python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py" \
  --sections "Scope & sources; Surface; Error model; Compatibility & versioning; Examples; Traceability; Contract files" \
  --ordered "steps/create-api-contract/api-contract.md"
```

A finding from either is remediated in the next contract-author iteration
(or, at iteration 3, fails the run) — never patched by you.

### Publish — the coordinator is the only writer of `api-contract.md`

Once the contract-reviewer passes and both checks are clean, publish the
draft. **The coordinator performs this step itself, never a subagent:** the
file-map write guard (`acs_lib/filemap.py`) denies any running `write`-kind
agent a write under the ticket docs tree, because the contract is a control
input the implementers of `/acs:code` are later checked against. Copy, never re-author:

```bash
cp "<partition>/steps/create-api-contract/api-contract.md" "<contract_path>"
```

Then commit `<contract_path>` on the ticket branch when it is inside the repo,
in the same commit as the machine-readable contract files the run changed (one
coherent "contract for <id>" commit). The partition draft is workspace state
and is never committed.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them in ONE grouped interaction (a
single AskUserQuestion containing all open questions as a numbered list), not
serial round-trips. Record each answer as its own `clarify.py add` entry (one
`C-<n>` per question, `--source` preserved). Never skip a question, merge two
questions into one entry, or auto-answer outside the existing
`--source assumption --rationale "..."` rule. Record every Q&A — obtained
interactively or relayed in a `/acs:ship` brief — with
`clarify.py add --skill create-api-contract --question "..." --answer "..." --ticket <id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`.

The questions this skill actually raises are compatibility questions, and they
are user decisions, not researchable facts: whether an existing consumer may be
broken, whether the change is versioned or in-place, how long a deprecated
field is kept, which error code an existing client already depends on. Ask
before specifying; a contract that guesses a breaking change is worse than no
contract.

If you genuinely cannot reach the user (a non-interactive run): do not guess.
Record the outgoing questions as `open` (`clarify.py add` without `--answer`),
write the result document with `"status": "interrupted"` and
`"stop_reason": "needs_input"` (`needs_input` is a stop reason, not a status —
the post-hook refuses any status but `completed | failed | interrupted`), run
the Finish steps, and return a `<handoff status="needs_input">` whose
`<questions>` carry them.

## Context pressure

If your context window is running low mid-run: do NOT burn the remainder on
work that would be lost. Commit any published contract and contract files on
the branch, flush in-flight state plus soft context (decisions, settled items,
gotchas) to `steps/create-api-contract/handoff-context.md`, then
run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, also on failure or handoff:

1. Write `steps/create-api-contract/result.json` per the
   result-document contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "outcome": "contract_written",
     "summary": "contract-reviewer passed with zero findings on iteration 2; contract published and committed",
     "states": {
       "contract_path": "docs/tickets/SHOP-123/api-contract.md",
       "items": 3,
       "traced_acs": ["AC-1", "AC-2", "AC-4"]
     },
     "findings": [],
     "errors": []
   }
   ```

   Canonical `states` keys — EXACT names; `acs step finish`
   documents them and the next steps read them:
   - `contract_path`: where `api-contract.md` was published (the ticket docs
     folder, or the partition when there is no checkout to anchor the docs
     folder to).
   - `items` (int): how many endpoints/commands/messages the contract
     declares — the same number as the front matter's `items` and as the
     `### ` subsections under `## Surface`.
   - `traced_acs` (list): the acceptance-criteria ids the items trace to, each
     appearing at least once in `## Traceability` (the union of the slices'
     reports when the contract-authors ran sliced).

   `outcome` is required on every `completed` result document — the post-hook
   refuses one without it, because this step completes in two ways: `contract_written`
   when the loop ran, `no_surface_owed` when the survey found no surface to
   specify (then `items` is `0` and `traced_acs` is `[]`). The pre-hook
   records `no_surface_owed` itself when the plan's `## Contract` block owes
   no contract, and this coordinator never runs.

   The machine-readable contract files are committed on the ticket branch, not
   recorded in `states`; name them in the completion report instead. On failure
   keep whatever is true: `contract_path` only when a contract was actually
   published, the open findings in `findings`, and the reason (iteration cap,
   needs input) in `summary`.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-api-contract.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — the run is not closed
   until it succeeds.

3. Report:
   - Direct invocation: a compact summary — the contract path, the items
     specified, which acceptance criteria they trace to, the compatibility
     verdict (backward compatible / breaking, and what was decided), the
     machine-readable contract files changed, open findings, and the next step
     (`/acs:create-test-docs <id>`).
   - Under `/acs:ship`: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` ≤1 KB, `<artifacts>` naming the
     published contract and the contract files, `<questions>` when
     `needs_input`, and `<next-step>/acs:create-test-docs <id></next-step>`.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed, interrupted,
or handed off — ends your final message with the standard block (INTERNALS.md
"Completion report"), rendered only AFTER the post-hook succeeded. Same labels,
same order, `none` where empty; under `/acs:ship` your final message is the
`<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-api-contract · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: contract path; items specified; acceptance criteria traced; compatibility verdict; machine-readable contract files changed
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <contract path, contract files, partition phase artifacts, branch>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:create-test-docs <ticket-id>`
```
