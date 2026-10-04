---
name: create-architecture
description: Bootstrap or regenerate the product's high-level design (HLD) — the overview, tech stack and cross-cutting conventions plus the HLD views the repo enabled at /acs:setup (C4 context, container and component views, conceptual data model, API landscape, deployment, project structure, and opt-in data-flow and capability maps), all Mermaid — from the PRD and the codebase, delivered as a docs-only PR on its own delivery ticket. Use after /acs:create-prd when starting a product, when onboarding acs onto an existing repo, or to regenerate the HLD after a major architectural shift. Not for a ticket's low-level design. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[delivery-ticket-id to resume | focus notes]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-architecture. You produce the product's
**high-level design** — the `hld/` part of the architecture set, wherever the
repo already keeps it, else at `docs/architecture/hld/` — judged against the
PRD, and ship it as a docs-only PR on a fresh delivery ticket. The low-level
design (`lld/<feature>/`) is not yours: the Design skills write it per ticket
(ADR-0118). This is a product-level skill: it is
ticket-independent and runs on its own — the PRD is its primary input, which
you look for yourself at Start, and when there is none it works from the
run's subject instead. You orchestrate two subagents — the
**architect**, which surveys and writes, and the **reviewer**, which judges —
and never write the architecture docs yourself.

## Start

MANDATORY first action — locate the PRD, before anything is allocated. Documents
are found, not configured: read CLAUDE.md and whatever docs index it or the repo
points at (e.g. `docs/README.md`), then Glob/Grep for `prd.md` or a PRD by
content. Found → that file is `<prd>`, and its roadmap (located the same way) is
`<roadmap>`.

None found → the skill still runs; it does not wait for /acs:create-prd. The
bar the architecture is judged against falls back to the run's subject: a
document `$ARGUMENTS` names (its goals, NFRs and constraints), else the focus
notes in `$ARGUMENTS` — and, on an existing codebase, the code itself. Tell
the user in one line: "no PRD found — working from <the subject>;
/acs:create-prd can baseline one later." Before the architect's first pass,
confirm the product goals, product-level NFRs and constraints the
architecture must satisfy (User interaction) and record each as its own
`clarify.py` entry; every task then carries `<constraint name="prd">none —
goals from C-<n>, …</constraint>` with those entries in `<context>`, and
they stand in for `<prd>` wherever this file names it.

Locate the architecture set the same way (an existing set is the directory
holding `hld/tech-stack.md`): found → that directory is `<architecture_dir>`;
none → `<architecture_dir>` = `docs/architecture/`, the conventional default.

Then run exactly one of:

- Fresh run (the normal case; each run gets its own delivery ticket):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-architecture --allocate --args "$ARGUMENTS"
```

- Resume: if `$ARGUMENTS` contains an existing delivery-ticket id (e.g.
  `SHOP-2` from a handoff `continue_with` command), do NOT allocate — rejoin
  that partition:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-architecture --ticket SHOP-2
```

If `acs step start` exits non-zero: stop immediately and surface its stderr to the
user verbatim. Otherwise parse the printed context JSON; the fields you need:
`partition`, `ticket_id`, `ticket`, `settings` (`tracker`, and `design.hld_types`
— the HLD types this repo writes), `agents`
(the agent name to spawn per role; the architect's and the reviewer's model and
effort come from `settings.models.create-architecture.<role>`, inheriting when
unset), `reconcile`, `handoff_summary`,
`post_hook`, `pipeline`, `checkout_root`.

The allocated delivery ticket is type `task`, titled
`Product architecture doc set` (`PRODUCT_TICKET_TITLES`); `acs step start` has
already created the partition, ticket.json, the lock, the session pointer,
and the `in_progress` run entry. If `settings.tracker.provider` is `github`,
sync the ticket out via `gh` per the tracker config.

## Resume & reconcile

If `context.reconcile` is true, verify recorded progress against reality
BEFORE continuing:

- Read `steps/create-architecture/` — the persisted
  `iter-<n>/<role>-message.xml` snapshots (`architect`, `reviewer`) tell you
  the last completed phase and iteration.
- Re-read the actual artifacts: which files under
  `<checkout_root>/<architecture_dir>/` exist and are complete; whether the
  ticket branch exists (`git branch --list`), is committed, pushed, or
  already has a PR (`gh pr list --head <branch>`).
- Distrust the record where it is cheap to re-check (a doc "written" but
  missing or truncated counts as not done).
- Continue from the first unfinished phase of the recorded iteration.
- An architect pass with no review → review it; a review with findings and
  no later architect pass → run the architect with those findings as
  `<context>`. The architect's authoring notes (`iter-<n>/authoring.md`)
  belong to their iteration.
- A sliced phase resumes slice by slice: re-run ONLY the slices whose own
  report is missing — a survey slice without `iter-1/authoring-<id>.md` or
  `iter-1/architect-<id>.json`, a gap-analyst slice without `iter-1/gaps-<id>.md`,
  a write slice without `iter-<n>/architect-write-<group>.json`, a reviewer
  slice without `iter-<n>/reviewer-<id>.md` — in one
  message, then redo the join with `acs.py notes merge`; the joined file is
  always rebuilt from the slice files, never trusted on its own.

If `context.handoff_summary` exists, read it plus
`steps/create-architecture/handoff-context.md` (if present),
do a light reconcile (spot-check the claimed artifacts), and continue from
where the summary points.

## Inputs & mode

The PRD is the primary input when there is one: read `<checkout_root>/<prd>`
and `<checkout_root>/<roadmap>` (absent → the recorded goals from Start stand
in for them). Then pick the mode:

- **Existing codebase** (the repo contains source beyond docs/config):
  reverse-engineer the CURRENT architecture from code and docs — manifests
  (package.json, pyproject.toml, go.mod, …), entrypoints, module layout,
  infra/CI files, existing READMEs. Open points (ambiguous boundaries,
  undocumented integrations) are confirmed with the user, not guessed.
- **Greenfield** (essentially empty repo): design the system to satisfy the
  PRD — goals, product-level NFRs, constraints drive every choice.
- **Re-run** (doc set already exists at `<architecture_dir>`): regenerate
  after major shifts — keep the same file set, update content in place. A
  file for a type the repo no longer enables is left as it is and named in
  the report; anything under `lld/` is never touched.

## Output contract

The architect writes EXACTLY these files under
`<checkout_root>/<architecture_dir>/hld/` — the three always-on documents plus
one file per type in `settings.design.hld_types` (ADR-0120; the catalog is
`acs_lib.design_types`) — and no other repo file:

| File | Type | Content | Diagram |
|------|------|---------|---------|
| `hld/overview.md` | always | system context, goals, quality attributes, constraints | — |
| `hld/tech-stack.md` | always | languages, frameworks, conventions | — |
| `hld/cross-cutting.md` | always | the conventions every feature follows: API (error model, auth, pagination, versioning, idempotency), data (naming, keys, audit columns, migration policy), the event envelope; security, observability, configuration | — |
| `hld/c4-context.md` | `c4-context` | C4 level 1 — system, users, external systems | `C4Context` (or `flowchart`) |
| `hld/c4-container.md` | `c4-container` | C4 level 2 — deployable containers, relations labelled with protocol | `C4Container` (or `flowchart`) |
| `hld/c4-component.md` | `c4-component` | C4 level 3 — components per container | `C4Component` (or `flowchart`) |
| `hld/data-model.md` | `data-model` | conceptual ERD — entities and relationships, no attributes | `erDiagram` |
| `hld/integration-map.md` | `integration-map` | API landscape — who exposes and consumes which API, style, sync or async, versioning and auth strategy | `flowchart` |
| `hld/deployment.md` | `deployment` | runtime and infrastructure topology | `flowchart` |
| `hld/project-structure.md` | `project-structure` | intended repo layout derived from the C4 container/component views — the canonical target a repo's structure is reviewed against | `flowchart` (directory-tree style) |
| `hld/data-flow.md` | `data-flow` | data-flow diagram with trust boundaries, for threat modelling | `flowchart` |
| `hld/capability-map.md` | `capability-map` | business capabilities mapped to containers | `mindmap` |

Rules: ALL diagrams are Mermaid (diffable, GitHub-rendered). C4 level 4
(code) is deliberately out of scope — the code and its API docs serve that
level. Detailed design — contracts, schemas, flows — is the low-level design
under `lld/<feature>/`, written per ticket by the Design skills; this skill
writes none of it and never touches `lld/`.

## Reflection loop — architect → review

The loop is architect -> review, max 3 iterations. Iteration 1 opens with a
**survey pass**: the architect decides the mode, inventories the PRD and the
codebase, fixes the canonical container/component vocabulary and records the
open points in its authoring notes, and writes no doc file. Once the user has
answered the open points, the **write pass** runs as parallel write slices, one
architect per HLD file group, all writing from the notes — which pinned the
shared vocabulary (the names of containers, components and entities), so each
group can be written without the others; ONE integration architect follows
only when a slice reports a seam — and the reviewer judges the result fresh,
itself sliced by dimension. On iterations 2-3 the reviewer's findings go
verbatim into the next write slices' `<task>` `<context>` and they author the
remediation. Decomposition is YOURS alone — subagents never
spawn subagents; every fan-out below is yours.

**What an iteration counts:** one architect -> review round (iteration 1's
survey pass belongs to iteration 1). `/acs:create-architecture` has no
path-driven review-depth selection: the cap is a fixed 3 on every run.

| Role | Kind | Agent | Spawn as |
|------|------|-------|------------|
| architect | write | `acs:create-architecture-architect` | `context.agents.architect` |
| gap-analyst | survey | `acs:create-architecture-gap-analyst` | `context.agents.gap-analyst` |
| reviewer | judge | `acs:create-architecture-reviewer` | `context.agents.reviewer` |

Spawn subagents with the Agent tool: subagent_type
`acs:create-architecture-architect` / `acs:create-architecture-gap-analyst` /
`acs:create-architecture-reviewer` (fall back to the un-namespaced name if
the runtime rejects the namespaced one). Spawn each role under the name in
`context.agents.<role>` — the plugin's `acs:create-architecture-<role>`, or the
generated `acs-create-architecture-<role>` copy `acs step start` wrote where
`settings.models` sets a model or effort for it. Model and effort travel with
that agent, so pass none of your own. If the runtime rejects the agent, FAIL the
run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops.

### Fan-out rules (every sliced phase)

- **One message, then wait for all.** The parallel instances of a phase are
  the SAME agent spawned N times in ONE message — one Agent call per slice,
  each `run_in_background: false` — and you wait for every one of them
  before the join. Cap: at most `settings.parallel.max_agents` (default 4)
  instances per message; more slices than that run in waves of that size, and
  the next phase starts only after the last wave is joined.
- **Slice ids.** Each instance's task and result carry `slice="<id>"`
  (`<task skill="create-architecture" phase="architect" slice="prd" …>`), so
  the SubagentStop snapshot lands at `iter-<n>/<role>-<id>-message.xml` and
  siblings never collide. A slice id is a short lowercase token (letters,
  digits, hyphens). The id `prd` is reserved for the survey slice below,
  `write-<group>` for the write slices and `integration` for the integration
  pass. A single, un-sliced instance omits `slice`
  exactly as before and writes the un-suffixed file names.
- **Per-slice files.** A sliced architect writes `iter-<n>/architect-<id>.json`
  and, as a survey slice, its notes to `iter-<n>/authoring-<id>.md`; a
  sliced reviewer writes `iter-<n>/reviewer-<id>.md`.
- **The join is deterministic** — never merge prose by hand:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-architecture/iter-<n>/authoring.md \
  <partition>/steps/create-architecture/iter-<n>/authoring-prd.md \
  <partition>/steps/create-architecture/iter-<n>/authoring-<area>.md …
```

  It merges by `## ` heading — the first file's preamble, each H2 once in
  first-seen order, the bodies concatenated in input order, each prefixed by
  a `<!-- slice: <id> -->` line — writes `--out`, prints `{ok, out,
  sections, inputs}`, and fails on a missing input. Every downstream reader
  (the write pass, the reviewer, its authoring-conformance dimension) reads
  the ONE joined file, each section once.

### Survey pass — iteration 1, sliced over disjoint repo areas

On an existing codebase whose source spans two or more disjoint top-level
areas (top-level packages, services or apps — e.g. `api/`, `web/`,
`worker/`), the survey is sliced: one `prd` slice plus one slice per area,
at most `settings.parallel.max_agents` per wave.

- **`prd`** owns the PRD, the roadmap, the existing docs (an existing set at
  `<architecture_dir>` included), the ADR-0012 doc-consistency step, and the
  notes' cross-cutting sections: Target doc set (the enabled file list and its
  PRD-driven outline), Reviewer checklist.
- **`<area>`** — the area's directory name, lowercased (`web-app/` →
  `web-app`; an area whose name is a reserved id or starts with `write-` is
  prefixed `area-`) — owns
  ONLY the files
  under its directory: the Mode evidence, the Inventory, the canonical names
  of the containers/components whose code lives there, the APIs it exposes
  or consumes (a counterpart another area owns is named by that area's
  directory path, and the write pass resolves it to the name the owning slice
  recorded), and its Risks & open decisions.
- The areas are disjoint directories, so no two slices should name the same
  component; where their notes still disagree (two areas claim one
  component, the Mode evidence conflicts), the write pass synthesizes them
  (below) — nobody silently picks one.

Each slice's task carries `<constraint name="area">` (its directory, or
`prd`) and it writes `iter-1/authoring-<id>.md` under the notes' standard
`## ` headings plus `iter-1/architect-<id>.json`. Join them with
`acs.py notes merge` into `iter-1/authoring.md`, the `prd` slice first so its
preamble leads. Greenfield or a single-area repo runs ONE un-sliced survey
architect, which writes `iter-1/authoring.md` itself.

A survey instance, sliced or not, writes no doc file. When it has open
reverse-engineering points it returns `needs_input` with them. Collect the
questions of ALL slices — and every drifted gap from the gap analysis below —
de-duplicate them, and ask everything in ONE grouped
clarification-ledger interaction (User interaction); the answers, recorded as
`C-<n>` entries, go to the write pass in `<context>`. The survey (the `prd` slice, when sliced)
also runs the shared ADR-0012 design-time doc-consistency step; any
findings surface through the same grouped ask.

### Gap analysis — beside the survey, iteration 1 (ADR-0122)

When `<architecture_dir>/hld/` already holds documents, the design and the code can
disagree, and the HLD must not be rewritten blind to it. Spawn the gap analysts
**in the SAME message as the survey** — one `acs:create-architecture-gap-analyst`
per survey area (slice id = the area's id; `repo` when the survey is un-sliced),
each `<constraint name="area">` the same directory, its `<inputs>` the existing
`hld/` files and the PRD — counted against the same cap,
`settings.parallel.max_agents` per wave. They run
while the survey runs. Join their notes once all have returned:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-architecture/iter-1/gaps.md \
  <partition>/steps/create-architecture/iter-1/gaps-<area>.md …
```

A greenfield repo, or one with no HLD yet, has nothing to compare: skip the gap
analysis and say so in the report. Each gap is handled by default as:

- **undocumented** (in the code, not in the HLD) → documented as built;
- **unimplemented** (in the HLD, not in the code) → kept, and marked planned
  (its document stays or becomes `proposed`/`approved`, the element drawn with the
  `planned` style);
- **drifted** (both, disagreeing) → a question in the survey's ONE grouped ask, with
  both readings and their citations — never silently resolved either way.

### Write pass — one architect per HLD file group

After the grouped ask, spawn the write slices: one architect per **HLD file
group** that holds at least one file this run writes (the always-on three plus
the enabled `hld_types`), all in ONE message — at most
`settings.parallel.max_agents` (default 4), waves of that size beyond it. The
partition rule is the file: every Output-contract file belongs to exactly one
group, so no two slices write the same file.

| Slice | Files (only the enabled ones) |
|-------|------------------------------|
| `write-context` | `hld/overview.md`, `hld/c4-context.md`, `hld/capability-map.md` |
| `write-structure` | `hld/c4-container.md`, `hld/c4-component.md`, `hld/deployment.md`, `hld/project-structure.md` |
| `write-data` | `hld/data-model.md`, `hld/integration-map.md`, `hld/data-flow.md` |
| `write-conventions` | `hld/tech-stack.md`, `hld/cross-cutting.md` |

`write-context` and `write-conventions` always run (they hold always-on
files); `write-structure` and `write-data` run when one of their types is
enabled. Each task carries `slice="write-<group>"`, `<constraint
name="files">` naming its group's files, and the same `<inputs>`: the joined
`iter-1/authoring.md`, `iter-1/gaps.md` when the gap analysis ran, and the
PRD; its `<context>` is the recorded answers (the drifted gaps' included), its
`<constraint name="hld_types">` the enabled types. A slice writes ONLY its
group's files, in the container/component/entity vocabulary the notes pinned —
never inventing a name — and reports `iter-<n>/architect-write-<group>.json`.
Create the branch (Delivery) before spawning them.

**Seams.** The groups meet where a file names what another group draws: the
container and component names of the C4 views, the entities of the data model,
the overview's links to the other files. The notes pin those names, so a slice
needs no sibling's output. A name a slice needed that the notes do not pin —
or a pinned name it found wrong — is a **seam**: it records it in its report's
`seams` (`[{"what": …, "file": …, "owner": "write-<group>"}]`, `[]` when
none) and writes the notes' name meanwhile. After the last wave:

- no slice reported a seam → skip the integration pass and go to review;
- any seam → spawn ONE more architect, alone, with `slice="integration"`. Its
  `<inputs>` name every slice's files and reports; it reconciles ONLY the
  reported seams — one name for one element across every file, cross-links
  that resolve — never a slice's substance, edits the files in place, and
  records each change (file, what, why, which slices) in
  `iter-<n>/architect-integration.json`. A conflict the evidence cannot settle
  comes back as `needs_input`.

The reviewer's `coherence` slice still judges cross-file naming
(internal-consistency): a seam nobody reported is a finding for the next
iteration.

**Survey synthesis.** When the survey was sliced, the write slices are the
consumers of the joined notes and each MUST reconcile them for the facts its
files use: where two survey slices' notes contradict each other, it records the
resolution with its evidence under a `## Synthesis` heading in
`iter-1/authoring-write-<group>.md`, or returns `needs_input` with the
contradiction as a question — never silently picks one. A resolution that
changes a name another group also uses is a seam, reported as above. Each
slice writes that file whenever the survey was sliced (its Synthesis says
"none" when nothing contradicted); redo the iteration-1 join with them
appended (`acs.py notes merge --out iter-1/authoring.md iter-1/authoring-prd.md
iter-1/authoring-<area>.md … iter-1/authoring-write-<group>.md …`), so
iteration 1's notes carry every `## Synthesis` entry the reviewer checks.

**Design versions (ADR-0122).** Every HLD file carries version front matter
(`status`, `version`, `tickets`), set only through `acs.py design`: a new file
gets `design init --ticket <delivery-ticket>` with `--status implemented` when it
documents the code as built and `--status proposed` when it designs ahead of the
code (greenfield, or a planned element); a changed file gets `design bump --ticket
<delivery-ticket>`, which re-opens it as `proposed`; a file the run leaves
unchanged keeps its block. Elements that are designed but not built are drawn with
a dashed `planned` classDef and marked `(planned)` in prose. The team's approval of
the docs PR is the design's approval; `/acs:docs-sync` later moves a design to
`implemented` when its code lands.

The architects write files only and never commit: you commit once, after
the review passes (Delivery).

On iterations 2-3 re-run only the write slices whose group's files the
findings name, each receiving ALL the reviewer's findings verbatim in
`<context>`; it fixes the ones in its files and records them under one
`## Findings addressed` heading in `iter-<n>/authoring-write-<group>.md`. A
finding that spans two groups' files (a cross-file naming inconsistency) goes
to the integration pass, which then runs after the re-run slices — alone, when
only such findings were open — and also whenever a re-run slice reports a
seam. Join the re-run slices' notes after the previous iteration's notes
(`acs.py notes merge --out iter-<n>/authoring.md iter-<n-1>/authoring.md
iter-<n>/authoring-write-<group>.md …`), so the notes the reviewer reads are
the pinned survey plus what was fixed.

Communicate in XML per `the SubagentStop hook's message check`; the `phase=`
of every task and result is the role (`architect`, `reviewer`). Example
survey architect task (un-sliced; a survey slice adds `slice="<id>"` and
`<constraint name="area">`; a write slice's objective is the write pass
for the files in its `<constraint name="files">`):

```xml
<task skill="create-architecture" phase="architect" ticket-id="SHOP-2" iteration="1">
  <objective>Survey pass: read the PRD and inventory the codebase; decide reverse-engineer vs greenfield; record the per-file outline of the enabled HLD types, the canonical component vocabulary and the open points in the authoring notes. Write no doc file.</objective>
  <inputs>
    <file>docs/product/prd.md</file>
    <file>docs/product/roadmap.md</file>
    <file>docs/architecture/</file>
  </inputs>
  <constraints>
    <constraint name="prd">docs/product/prd.md</constraint>
    <constraint name="architecture_dir">docs/architecture</constraint>
    <constraint name="hld_types">c4-context, c4-container, c4-component, data-model, integration-map, deployment, project-structure</constraint>
    <constraint name="diagrams">Mermaid only: C4Context/C4Container/C4Component or flowchart, erDiagram, mindmap; C4 level 4 out of scope.</constraint>
    <constraint name="naming">Fix the canonical container/component names in the authoring notes; every HLD file uses this vocabulary.</constraint>
    <constraint name="required_sections:hld/overview.md">System context; Goals; Quality attributes; Constraints</constraint>
    <constraint name="required_sections:hld/tech-stack.md">Languages; Frameworks; Conventions</constraint>
    <constraint name="required_sections:hld/cross-cutting.md">API conventions; Data conventions; Security; Observability</constraint>
    <constraint name="required_sections:hld/project-structure.md">Directory layout</constraint>
    <constraint name="audience_style_profile">engineers/architects (technical, diagram-heavy)</constraint>
  </constraints>
</task>
```

Validate EVERY message you send and receive — the SubagentStop hook checks
each one a subagent returns and reports why it is invalid. On an invalid
message, re-request it once; if still invalid, fail the run
with the validation error recorded in `errors`.

Every phase output is persisted at the phase boundary, BEFORE the next
phase starts: the SubagentStop hook snapshots each returned message to
`steps/create-architecture/iter-<n>/<role>-message.xml` (a sliced instance:
`iter-<n>/<role>-<id>-message.xml`); if that snapshot is missing (a host
that does not fire the hook), write the `<task>` and `<result>` there
yourself. The architects' own artifacts are `iter-<n>/authoring.md` (Mode;
Inventory; Target doc set with the per-file outline; Risks & open decisions;
Reviewer checklist — the Upstream inventory cites every PRD and codebase fact
verbatim — joined from `iter-<n>/authoring-<id>.md` when sliced) and
`iter-<n>/architect.json` (`iter-<n>/architect-<id>.json` per slice — survey,
write and integration); the reviewer's is
`iter-<n>/reviewer.md`, joined from `iter-<n>/reviewer-<id>.md`. Every
iteration's reviewer `<inputs>` name that iteration's joined authoring notes.

Phases:

1. **Architect** — the survey pass (iteration 1 only), the grouped ask, then
   the write slices and, when a seam was reported, the integration pass, all
   as above. On iterations 2-3 the reviewer's findings go verbatim into the
   re-run write slices' `<task>` `<context>`.
2. **Review** — after the write pass finishes, spawn the reviewer
   slices on its result. The reviewer has ten check dimensions, so the
   review is sliced by dimension: three fresh instances of the SAME
   `acs:create-architecture-reviewer` agent in ONE message, each task
   carrying `<constraint name="dimensions">` with its dimension numbers:

   | Slice | Dimensions (numbers as in the reviewer agent) |
   |-------|-----------------------------------------------|
   | `coverage` | 1 doc-set-completeness · 2 prd-coverage · 3 codebase-match · 8 docs-only-changeset |
   | `diagrams` | 4 mermaid-diagrams — the ONLY slice that runs `mermaid_lint.py` · 6 diagram-prose-agreement |
   | `coherence` | 5 internal-consistency · 7 authoring-conformance · 9 structure — the ONLY slice that runs `structure_lint.py` · 10 audience-style |

   Grounding policing applies in every slice. Each slice writes
   `iter-<n>/reviewer-<id>.md`; join them with `acs.py notes merge --out
   iter-<n>/reviewer.md iter-<n>/reviewer-coverage.md
   iter-<n>/reviewer-diagrams.md iter-<n>/reviewer-coherence.md`. The slices
   own disjoint dimensions, so the join is the synthesis, plus one
   **de-duplication** step: drop a finding that cites the same location and
   the same defect as another slice's finding, keeping the higher severity,
   and say so in the joined report — append a `## De-duplicated findings`
   section naming each dropped finding and the one it duplicates (re-apply
   it whenever the join is redone). The de-duplicated findings are the ones
   the pass rule and the next write pass see. It judges fresh from
   artifacts only (never the architects' reasoning), against the dimensions
   in the reviewer agent, all blocking.

   The reviewer's `<inputs>` include `iter-1/gaps.md` when the gap analysis ran.
   The reviewer task's `<constraints>` also carry `hld_types`, each in-scope
   file's `required_sections:<file>` and the `audience_style_profile`
   declared in the architect task example above — the single-diagram HLD
   files stay outside the structure floor (covered instead by dim-1
   `doc-set-completeness` and the diagram-lint gate).

**Pass rule.** The iteration passes only if EVERY reviewer slice returned
`status="completed"` with zero blocking findings — zero reviewer findings =
pass — proceed to Delivery. Any slice's blocking finding blocks, and ALL
slices' findings go verbatim to the next write pass. A slice that failed or
returned no usable result fails the iteration: never "pass with a missing
slice". On findings (the joined `iter-<n>/reviewer.md` holds them), feed
them verbatim into the next iteration's architect `<task>` `<context>` and
re-run architect -> review. After iteration 3 with findings
remaining: stop, final status `failed`, findings recorded in the result
document; commit whatever was written to the local ticket branch so
nothing is lost, but do NOT push or open the PR.

## Delivery (branch, commit, PR)

The delivery-ticket pattern, done by you
(/acs:create-design and /acs:code are not involved):

1. **Branch** (before the write slices write): require a clean working
   tree (`git status --porcelain` empty — if not, ask the user before
   proceeding). Name the branch
   `<type>/<ticket_id>-<slug>` with `type=task`, the ticket id, and the
   slugified title — e.g. `task/SHOP-2-product-architecture-doc-set` — and
   `git checkout -b` it from the default branch.
2. **Commit** (after the reviewer passes): stage ONLY
   `<architecture_dir>/` and verify the diff is docs-only
   (`git diff --cached --name-only` — every path under
   `<architecture_dir>`). Commit in the repo's own style, naming the ticket id
   (default `<ticket_id> <summary>`), e.g.
   `SHOP-2 Add product architecture doc set` (or `Regenerate …` on re-run).
3. **Push & PR**: `git push -u origin <branch>`, then follow
   `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/delivery-pr.md` — the label,
   the PR title, the body template, the pre-open self-check, `gh pr
   create`, and recording `{number, url, branch}` for the result document.
   Nothing about this skill changes those steps.

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
`clarify.py add --skill create-architecture --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

Ask clarifying questions when genuinely ambiguous (AskUserQuestion or plain
questions) — at minimum: confirm open reverse-engineering points on existing
codebases. A sliced
survey's open questions — every slice's — go into that ONE grouped ask. Do not
ask about things the PRD or the code already answers.

If you genuinely cannot reach the user (e.g. a non-interactive run), do not
guess — run Finish with `status: "interrupted"` and
`stop_reason: "needs_input"`, then return a `<handoff skill="create-architecture"
ticket-id="<id>" status="needs_input">` with the `<questions>` list instead.

## Context pressure

If your context is running low mid-run: flush in-flight work plus soft
context (mode decision, confirmed answers, partial reviewer findings,
gotchas) to `steps/create-architecture/handoff-context.md`,
then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints (re-running this skill
with the delivery-ticket id resumes via the Start section's resume form).

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/create-architecture/result.json` per the
   result-document contract in INTERNALS.md. Canonical `states` keys (exact
   names): `architecture` and `pr`. `hld` entries are paths relative to
   `<path>/hld/`:

```json
{
  "status": "completed",
  "summary": "doc set reviewed against PRD and codebase; docs-only PR opened",
  "states": {
    "architecture": {
      "path": "docs/architecture",
      "hld": ["overview.md", "tech-stack.md", "cross-cutting.md", "c4-context.md", "c4-container.md", "c4-component.md", "data-model.md", "integration-map.md", "deployment.md", "project-structure.md"]
    },
    "pr": {"number": 7, "url": "https://github.com/owner/repo/pull/7", "branch": "task/SHOP-2-product-architecture-doc-set"}
  },
  "findings": [],
  "errors": []
}
```

   On failure: `status: "failed"`, the blocking findings in `findings`, the
   reason in `summary`, keep whatever is true in `states` (e.g. the
   written `architecture` files without `pr`). On
   handoff you write no result document: the Context-pressure path's
   `handoff.py` finalizes the step `interrupted` with
   `stop_reason: context_pressure` and records its summary on the invocation.
   (`handed_off` is not a status and `handoff_summary` is not a result field.)

2. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-architecture.py" --result-file "<the result.json you just wrote>"
```

3. Report a compact summary to the user: mode, files written, review
   iterations, PR URL, and that /acs:merge-pr (after their review) lands it
   — for a greenfield product, the next step once merged is to ticket the
   scaffold (`/acs:create-ticket "Scaffold the repository per the architecture
   docs"`) and ship it. If you genuinely cannot reach the user (a non-interactive run),
   return ONLY the `<handoff>` XML as your final message: status, summary under 1 KB,
   artifact refs (doc-set path, result.json, PR URL), and `<next-step>`.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-architecture · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: HLD files written at `<architecture_dir>/hld/` (and the enabled types); delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the docs PR; then `/acs:create-ticket` (greenfield: a scaffold ticket first, then `/acs:ship` it)
```
