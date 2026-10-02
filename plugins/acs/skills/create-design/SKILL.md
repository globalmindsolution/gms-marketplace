---
name: create-design
description: Settle the system design for a design-significant ticket before implementation is specified — analyze the ticket, codebase, and architecture docs, weigh multiple options with trade-offs, and produce an approved design.md in the ticket's docs folder. Use when a ticket carries needs_design true (always for epics) and no approved design exists yet; tickets without the flag skip straight to /acs:code. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-design. Your job: turn a design-significant
ticket (`needs_design: true`) into an approved `design.md` in the ticket's docs
folder — context, at least two genuinely-weighed options, a decision with
rationale, the architecture of the change, risks, and rollout — judged by a fresh
design reviewer before it gates `/acs:code`. You orchestrate two subagents over
XML — the **designer**, which surveys the decisions and options and writes the
draft, and the **design reviewer**, which judges it (designer → design review);
you never write the design content yourself.

The pre-hook (`pre-create-design.py`) checks this skill's SUBJECT, never its
place in any order and never whether an upstream artifact exists: settings
exist, the ticket resolves to a live, unlocked partition, and the ticket
carries `needs_design: true`. It does NOT check that a `/acs:create-ticket`
run is recorded completed — the partition existing IS the ticket having been
created — nor that an analysis or architecture doc set exists: the skill
works from what it finds (Inputs below). Pipeline order lives in
`workflows/ship.yaml`, not in the gate. Epic children inherit the EPIC's design —
this skill runs on the epic (or a design-flagged story/task), never on a child;
a child carries `needs_design: false`, so the flag check blocks it automatically.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-design
```

- If it exits non-zero: STOP and surface its stderr verbatim to the user. Do not
  improvise a workaround.
- Parse the printed context JSON. Fields you will use: `partition` (the ticket
  directory — all state lives here), `ticket` (full ticket doc: type, description,
  acceptance criteria, parent, children), `ticket_id`, `settings` (notably
  `formats` and `enforcement.design_sections`),
  `agents` (the agent name to spawn per role; each role's model and effort come
  from `settings.models.create-design.<role>`, inheriting when unset), `reconcile`,
  `handoff_summary`, `design`, `pipeline`, `post_hook`, `checkout_root`
  (consumer repo root).
- Locate the repo documents this skill reads, once, the way any session finds
  a document: CLAUDE.md and whatever docs index it or the repo points at
  (e.g. `docs/README.md`), then a Glob/Grep by file name or content. Record
  them repo-relative: `<architecture_dir>` (the folder holding
  `hld/tech-stack.md`), `<prd>` (the PRD file), `<standards_dir>` (the
  standards set) — each absent when not found — and `<adr_dir>`, the repo's
  ADR folder, else `docs/adr/`. Subagents receive the folders as task
  constraints (`architecture_dir`, `adr_dir`, `standards_dir`) and the files
  by path in `<inputs>`; they never look a location up in settings.

Throughout this file `<partition>` means the `partition` path from the context JSON
and `<id>` means `ticket_id` (e.g. `SHOP-123`).

### Design artifact resolution

`design.md` is the ticket's design — ONE file per ticket, one name, on every
run. It is a human-facing document: it lives in the ticket's docs folder in
the consumer repo, beside the ticket, the analysis and the plan (ADR 0090).
Resolve where it lives before anything else:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" artifacts show --ticket <id>
```

- `artifacts["design.md"]` non-null → that existing file is the design; this
  run REVISES it in place (a re-design after new information, never a second
  file).
- else `docs_dir` non-null → the design is published to `<docs_dir>/design.md`.
- else (no checkout to anchor the docs folder to) → the design is
  published to `<partition>/design.md` and nothing enters the repo.

This is exactly what `acs_lib.artifacts.artifact_path` resolves and what the
`design_approved` predicate and `/acs:code` look for, so the path this run
chooses is the path that opens the next gate. Call it `<design_path>` below.

The working draft lives at `steps/create-design/design.md`; the
published file is a copy of those exact bytes (see Publish). The draft is
workspace state — the designer writes it and the design reviewer judges it,
and the file-map guard denies any subagent a write under the ticket docs tree.

## Resume & reconcile

- If `context.reconcile` is true (the step's
  previous invocation ended `interrupted` or `failed`; `context.prior_status`
  says which): verify recorded progress against reality BEFORE continuing —
  list `steps/create-design/iter-*/*-message.xml`, re-resolve the design
  artifact (above) and re-read the draft and `<design_path>` if they exist, and
  check whether their content actually
  matches the last persisted phase output. Trust nothing you cannot see in a
  file: a design recorded published that is not on disk is not published.
  Continue from the first unfinished
  phase/iteration; never redo work that demonstrably holds, never trust work
  you cannot see in an artifact.
- If `context.handoff_summary` exists: read it plus
  `steps/create-design/handoff-context.md` (when present), do a light
  reconcile (spot-check the named artifacts), and continue from where it points.
- Continue from the first unfinished phase — a designer pass with no
  review → review it; a review with findings and no later designer pass →
  run the designer with those findings as `<context>`. The designer's
  authoring notes (`iter-<n>/authoring.md`) belong to their iteration.
- A sliced phase resumes slice by slice: re-run ONLY the slices whose own
  report is missing — the scope pass without `iter-1/authoring-scope.md`, a
  research slice without `iter-1/authoring-<id>.md` or
  `iter-1/designer-<id>.json`, a draft pass without `iter-1/designer.json`
  (or, after a research pass, `iter-1/authoring-synthesis.md`), a design-reviewer slice without
  `iter-<n>/design-reviewer-<id>.md` — in one message, then redo the join
  with `acs.py notes merge`; a joined file is always rebuilt from its slice
  files, never trusted on its own.
- Fresh run (`reconcile` false): start at iteration 1, designer phase.

## Inputs — gather before the loop

Read (you and your designer; reference by path in XML, do not inline file bodies):

1. The ticket document (`ticket.md` in the docs folder, or `ticket.json` in the
   partition — whichever `acs.py artifacts show` reports as `source_path`):
   title, description, acceptance criteria, type, priority, children.
2. **The product architecture doc set — PRIMARY input when it exists**:
   `<checkout_root>/<architecture_dir>/` (conventionally `docs/architecture/`):
   `hld/overview.md`, `hld/c4-context.md`, `hld/c4-container.md`,
   `hld/c4-component.md`, `hld/data-model.md`, `hld/deployment.md`,
   `hld/tech-stack.md`, `lld/flows/*.md`, `lld/contracts.md`. The design either
   CONFORMS to this doc set or explicitly lists the architecture changes it
   requires (which /acs:code later applies to the doc set). If the doc set is
   absent, note that in design.md and design against the codebase directly.
3. The PRD at `<checkout_root>/<prd>` when present —
   product-level NFRs and constraints bound the design.
4. The consumer repo's code and docs relevant to the ticket (the designer's
   survey identifies the exact files).

Any of 2-4 may be absent; the ticket itself is always there, and the design
is then grounded in the ticket and the codebase as it is.

## Reflection loop — designer → design review

The loop is designer → design review, max 3 iterations. Weighing the options
and writing them down are one act — the decisions and trade-offs the survey
records are the draft's own sections — so one role does both, in three
passes on iteration 1: the **scope pass** surveys the ticket, the
architecture doc set and the codebase and lists the major decisions; the
**option-research pass** weighs each major decision's options in parallel,
one designer per decision; the **draft pass** — a single designer, because
`design.md` is ONE document and cannot be split into disjoint files —
authors the design draft from the joined notes. The design reviewer then
judges the result fresh, itself sliced by dimension. On iterations 2-3 the
design reviewer's findings go verbatim into the next designer `<task>`
`<context>` and the designer authors the remediation. Decomposition is YOURS
alone — subagents never spawn subagents; every fan-out below is yours.

**What an iteration counts:** one designer → design review round.
`/acs:create-design` has no path-driven review-depth selection: the cap is
a fixed 3 on every run.

| Role | Kind | Agent | Spawn as |
|------|------|-------|------------|
| designer | write | `acs:create-design-designer` | `context.agents.designer` |
| design-reviewer | judge | `acs:create-design-design-reviewer` | `context.agents.design-reviewer` |

For every phase:

1. Compose a `<task>` per `the SubagentStop hook's message check`:

   ```xml
   <task skill="create-design" phase="designer" slice="scope" ticket-id="SHOP-123" iteration="1">
     <objective>Scope pass: survey the ticket, architecture doc set, and codebase; record the major design decisions (ids d1, d2, …), candidate options (>=2 per decision) and the genuinely-open points needing user input in iter-1/authoring-scope.md. Write no draft.</objective>
     <inputs>
       <file>/abs/repo/docs/tickets/SHOP-123/ticket.md</file>
       <file>/abs/repo/docs/architecture/hld/c4-container.md</file>
       <file>/abs/repo/docs/architecture/lld/contracts.md</file>
     </inputs>
     <constraints>
       <constraint name="architecture_dir">docs/architecture</constraint>
       <constraint name="adr_dir">docs/adr</constraint>
       <constraint name="architecture">Conform to docs/architecture or list every doc-set change the design requires</constraint>
       <constraint name="nfr">Cover security and performance explicitly</constraint>
     </constraints>
   </task>
   ```

2. Validate EVERY message you send and receive — the SubagentStop hook
   checks each one a subagent returns and reports why it is invalid. On an
   invalid message from a subagent: re-request once with the validation
   error quoted; still invalid →
   fail the run, recording the error in `errors`.

3. Spawn the subagent with the Agent tool, `subagent_type` as below (fall back to
   the un-namespaced name only if the runtime rejects the namespaced one). The
   `phase=` of every task and result is the role (`designer`,
   `design-reviewer`). Spawn each role under the name in `context.agents.<role>`
   — the plugin's `acs:create-design-<role>`, or the generated
   `acs-create-design-<role>` copy `acs step start` wrote where
   `settings.models` sets a model or effort for it. Model and effort travel
   with that agent, so pass none of your own. If the runtime rejects the
   agent, FAIL the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

4. The phase's `<task>` and `<result>` are persisted at the phase boundary,
   BEFORE the next phase starts: the SubagentStop hook snapshots each
   returned message to `steps/create-design/iter-<n>/<role>-message.xml`
   (a sliced instance: `iter-<n>/<role>-<id>-message.xml`);
   if that snapshot is missing (a host that does not fire the hook), write
   it yourself. The designer's own artifacts are `iter-<n>/authoring.md`
   (its survey: Analysis; Decisions & candidate options with trade-offs;
   NFR checklist; Architecture conformance call; Open questions; Risks;
   Reviewer checklist — on iteration 1 joined from the scope and research
   slices' `iter-1/authoring-<id>.md`) and `iter-<n>/designer.json`
   (`iter-<n>/designer-<id>.json` per slice); the design reviewer's is
   `iter-<n>/design-reviewer.md`, joined from its slices'
   `iter-<n>/design-reviewer-<id>.md`. Every iteration's design-reviewer
   `<inputs>` name that iteration's joined authoring notes.

### Fan-out rules (every sliced phase)

- **One message, then wait for all.** The parallel instances of a phase are
  the SAME agent spawned N times in ONE message — one Agent call per slice,
  each `run_in_background: false` — and you wait for every one of them
  before the join. Cap: at most `max_parallel = 4` instances per phase;
  more slices than that run in waves of 4, and the next phase starts only
  after the last wave is joined.
- **Slice ids.** Each instance's task and result carry `slice="<id>"`
  (`<task skill="create-design" phase="designer" slice="d1" …>`), so the
  SubagentStop snapshot lands at `iter-<n>/<role>-<id>-message.xml` and
  siblings never collide. A slice id is a short lowercase token (letters,
  digits, hyphens). A single, un-sliced instance omits `slice` and writes
  the un-suffixed file names.
- **The join is deterministic** — never merge prose by hand:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-design/iter-1/authoring.md \
  <partition>/steps/create-design/iter-1/authoring-scope.md \
  <partition>/steps/create-design/iter-1/authoring-d1.md <…/authoring-d2.md> …
```

  It merges by `## ` heading — the first file's preamble, each H2 once in
  first-seen order, the bodies concatenated in input order, each prefixed by
  a `<!-- slice: <id> -->` line — writes `--out`, prints `{ok, out,
  sections, inputs}`, and fails on a missing input. The draft designer and
  the design reviewer read the ONE joined file, each section once.

### Phase: designer — `acs:create-design-designer`

Objective, iteration 1: from ticket + architecture docs + codebase, survey
the decisions to make, >=2 candidate options per major decision with
preliminary trade-offs, the affected components/flows/data, the NFR
checklist (security, performance at minimum), and the genuinely open points
(user-preference or business trade-offs, not researchable facts) — recorded
in the authoring notes — then write the design draft from them. The designer
also runs the shared ADR-0012 design-time doc-consistency step; any findings
surface through the "Clarification ledger first" mechanism below (User
interaction). Iteration 1 runs that objective as three passes and a join:

1. **Scope pass** — ONE designer, `slice="scope"`, writes no draft: the
   whole survey above into `iter-1/authoring-scope.md` (every section of the
   notes), with each major decision given a short id `d1`, `d2`, … and
   its preliminary options, plus `iter-1/designer-scope.json`; it also runs
   the ADR-0012 doc-consistency step.
2. **Option-research pass — parallel, when the scope notes list two or more
   major decisions.** One designer per major decision, `slice="<decision
   id>"`, all spawned in ONE message (cap 4 per wave), each task carrying
   `<constraint name="decision">` with that decision's id and one-line
   statement and the scope notes in `<inputs>`. The partition is by
   decision: a research slice researches ONLY its own decision — its
   candidate options (>=2 genuinely viable, how each works), their
   trade-offs against the NFR checklist and constraints, the code and doc
   evidence, and that decision's genuinely open points — and writes ONLY
   `iter-1/authoring-<id>.md` (sections `## Decisions & candidate options`,
   `## Open questions`, `## Risks`) and `iter-1/designer-<id>.json`; it never
   touches the draft or another decision's file, so the slices cannot
   overlap. With fewer than two major decisions there is nothing to split:
   skip this pass — the scope notes' options stand.
3. **Join** — `acs.py notes merge --out iter-1/authoring.md
   iter-1/authoring-scope.md iter-1/authoring-<id>.md …` (scope first, then
   the research slices in decision order; with no research pass, the scope
   file alone). The joined file is iteration 1's authoring notes.

Any pass may return `needs_input` with `<questions>` for genuinely open
points. Hold the scope pass's questions until the research pass has
finished, then resolve every pass's questions together in ONE grouped
interaction (User interaction below) and give the draft designer the
answers in `<context>`.

4. **Draft pass** — ONE designer, un-sliced, with the joined
   `iter-1/authoring.md` in `<inputs>`, writes the draft (below) and
   `iter-1/designer.json`. It is the single consumer of the research slices,
   so it MUST synthesize them, not just read their join: where two slices'
   notes (or the scope notes and a research slice) contradict each other —
   one option's cost or feasibility claimed differently, an NFR bound, a
   shared component described two ways — it records the resolution with its
   evidence under a `## Synthesis` heading in `iter-1/authoring-synthesis.md`,
   or returns `needs_input` with the contradiction as a question; never
   silently picks one. After the draft pass, redo the join with that file
   appended (`acs.py notes merge --out iter-1/authoring.md
   iter-1/authoring-scope.md iter-1/authoring-<id>.md …
   iter-1/authoring-synthesis.md`), so iteration 1's notes — the ones the
   design reviewer judges against — carry the Synthesis. With no research
   pass there is nothing to synthesize and the file is not written. The
   draft pass writes no other authoring notes on iteration 1 — the joined
   notes are that iteration's notes. On iterations 2-3 a single
   designer, un-sliced, revises the draft and writes that iteration's full
   `iter-<n>/authoring.md` itself (with its Findings addressed section): the
   draft is one document, so the write never fans out — and with one writer
   there is no integration pass to run (it is skipped when only one writer
   ran). If the draft
   designer returns `needs_input` with `<questions>`, resolve them in "User
   interaction" below and re-run the designer for the same iteration with
   the answers in `<context>`.

The draft: write it at `steps/create-design/design.md`
(the designer mutates ONLY the workspace partition — never the consumer repo, and
never the ticket docs tree, which the file-map guard denies it; the coordinator
publishes the verified draft to `<design_path>` in Publish below). Required
sections, exactly these headings:

```markdown
# Design — <id>: <ticket title>

## Context & constraints
   Problem, scope, assumptions; binding constraints from PRD/architecture/codebase;
   NFRs — security and performance REQUIRED, plus others that apply
   (availability, cost, operability, compliance).
## Options considered
   >= 2 real options (### Option A/B/...), each with how it works and explicit
   trade-offs (pros/cons vs. the NFRs and constraints). No strawmen.
## Decision & rationale
   The chosen option, why it wins, why the others lose. One-line decision
   statement first — it becomes states.decision.
## Architecture
   Components (new/changed, mapped to the C4 container/component views),
   interfaces/contracts (signatures, payloads, error shapes), data model changes
   (Mermaid ER when entities change), and Mermaid sequence diagrams for every
   new or changed runtime flow.
   ### Architecture conformance
   Either "Conforms to <architecture_dir> — no doc-set changes required" or
   "Required architecture changes": exact list of doc-set files /acs:code must
   update (e.g. hld/c4-container.md, hld/data-model.md, lld/flows/<flow>.md,
   lld/contracts.md) and what changes in each.
## Impact & risks
   Blast radius, affected tickets/components, risks with mitigations.
## Rollout/migration
   Ordering, data/schema migration, feature flags, backward compatibility,
   rollback plan (or "single-step deploy, no migration" with justification).
```

The designer and design-reviewer tasks both carry two declared constraints —
`required_sections` and `<constraint name="audience_style_profile">reviewers
(decision + trade-off narrative)</constraint>` — mirroring `create-prd/SKILL.md`'s
precedent.

`required_sections` is settings-sourced, NOT a hardcoded literal: the coordinator
RESOLVES the configured `settings.formats.design_template` (default
`design-default`) exactly as `create-pr` resolves `pr_description_template` — a
built-in name (`design-default`) maps to `${CLAUDE_PLUGIN_ROOT}/templates/<name>.md`;
otherwise `<checkout_root>/.acs/templates/<name>.md`; otherwise an absolute path —
and passes `settings.enforcement.design_sections` (the section list defaulted from
that template) as the constraint on the designer and design-reviewer tasks:
`<constraint name="required_sections">Context &amp; constraints; Options considered;
Decision &amp; rationale; Architecture; Impact &amp; risks; Rollout/migration</constraint>`
(the same six headings above). Because `enforcement.design_sections` defaults to
exactly that list, an absent `design_template`/`design_sections` key yields the
identical constraint — byte-identical to the prior hardcoded gate. A consumer repo
that supplies its own `<checkout_root>/.acs/templates/design-default.md` (or a
custom-named template plus a matching `enforcement.design_sections`) has its
`design.md` gated against ITS sections. The `audience_style_profile` constraint
(MAR-150) is unchanged.

The designer adds a subsection
`### Decision records` under "Decision & rationale" listing each accepted
decision as a one-line ADR title and noting: "/acs:docs-sync commits these as
ADRs under `<adr_dir>` once the changeset exists." `/acs:code` no longer
authors ADR or other general doc updates (MAR-65); `/acs:docs-sync`'s
doc-updater is the sole producer, and its `adr` doc area commits the binding
design's accepted decision records. Designer and design-reviewer tasks both
carry `adr_dir`.

All diagrams are Mermaid. The design references architecture docs by path; it
never copies them wholesale. For an epic: design at epic level — children
INHERIT this design via cross-partition read in their /acs:code; never
duplicate or split it into child partitions. The design a child reads is the
EPIC's `design.md`, resolved the same way (its docs folder, else its
partition).

Only the option-research pass above runs designers in parallel, and only
because its slices own disjoint files (`iter-1/authoring-<id>.md`, one per
decision). Two designers never touch the draft in the same iteration. The
design reviewer runs after ALL designers finish and judges the combined
result. On iterations 2-3 the design reviewer's findings go verbatim into
the designer `<task>`'s `<context>`.

### Phase: design-reviewer — `acs:create-design-design-reviewer`

The design-reviewer `<task>`'s `<constraints>` always carry `required_sections` and
`audience_style_profile` (declared above in the designer phase), alongside `adr_dir`
and, when Start found a standards set, `standards_dir` (see below).

The design reviewer has eight check dimensions, so the review is sliced by
dimension: three fresh instances of the SAME
`acs:create-design-design-reviewer` agent spawned in ONE message, each task
carrying `slice="<id>"` and `<constraint name="dimensions">` with its
dimension numbers:

| Slice | Dimensions (numbers as in the design-reviewer agent) |
|-------|------------------------------------------------------|
| `decision` | 1 alternatives · 3 feasibility · 4 nfr (with its `standards` sub-check) |
| `conformance` | 2 consistency (with its `standards` sub-check) · 8 authoring-conformance |
| `form` | 5 completeness — the ONLY slice that runs `mermaid_lint.py` · 6 structure — the ONLY slice that runs `structure_lint.py` · 7 audience-style |

Grounding policing applies in every slice. Each slice writes
`iter-<n>/design-reviewer-<id>.md`; join them with `acs.py notes merge --out
iter-<n>/design-reviewer.md iter-<n>/design-reviewer-decision.md
iter-<n>/design-reviewer-conformance.md iter-<n>/design-reviewer-form.md`.
The slices own disjoint dimensions, so the join is the synthesis, plus one
**de-duplication** step: drop a finding that cites the same location and
the same defect as another slice's finding (a diagram defect both
`consistency` and `completeness` saw, say), keeping the higher severity,
and say so in the joined report — append a `## De-duplicated findings`
section naming each dropped finding and the one it duplicates (re-apply it
whenever the join is redone). The de-duplicated findings are the ones the
pass rule and the next designer see.

Spawn fresh — it sees artifacts (the design draft, ticket, architecture docs,
code), never the designer's reasoning. Its `<inputs>` name the draft at
`steps/create-design/design.md`: the design reviewer judges the bytes
Publish then copies, so nothing unverified reaches `<design_path>`. It checks,
each a finding `dimension`:

- `alternatives` — >=2 options genuinely weighed with real trade-offs, not strawmen;
- `consistency` — design agrees with the actual codebase and the architecture
  doc set; the conformance subsection is accurate and complete; also runs a
  `standards` sub-check against the standards set at `standards_dir` when set,
  emitting `dimension="standards"` findings for design decisions this
  design.md introduces (changeset-scoped block/surface, graceful
  degradation when unset);
- `feasibility` — implementable with the documented tech stack and constraints;
- `nfr` — security and performance (and other applicable NFRs) concretely
  addressed, not hand-waved; the same `standards` sub-check also applies to
  NFR-shaped `standards/` content (testing-conventions, review-checklist
  performance/security/operability criteria);
- `completeness` — all required sections present and substantive; Mermaid
  diagrams present for new/changed flows and syntactically plausible.

When Start located a standards set, `standards_dir` is passed into the
design-reviewer `<task>`'s `<constraints>` (present only when found) — mirroring how
`code/SKILL.md` conditionally passes `e2e_command`/`e2e_setup`/
`e2e_teardown`/`e2e_per_iteration`.

ALL findings block — zero findings = pass. **Pass rule:** the iteration
passes only if EVERY design-reviewer slice returned `status="completed"`
with zero blocking findings; any slice's blocking finding blocks, and ALL
slices' findings go verbatim to the next designer. A slice that failed or
returned no usable result fails the iteration: never "pass with a missing
slice". On findings (the joined `iter-<n>/design-reviewer.md` holds them),
feed every finding verbatim into the next iteration's designer `<task>`
`<context>` and re-run designer → design review. After iteration 3 with findings remaining: stop;
final status `failed`, findings recorded in result.json.

### Publish — the coordinator is the only writer of the published `design.md`

Once the design reviewer passes with zero findings, publish the draft. **The
coordinator performs this step itself, never a subagent:** the file-map write
guard (`acs_lib/filemap.py`) denies any running `write` agent (the designer)
a write under the ticket docs tree, because these documents are precisely
the control inputs a writing agent is checked against. Copy, never re-author — the published bytes must
equal the verified bytes:

```bash
cp "<partition>/steps/create-design/design.md" "<design_path>"
```

Committing it: `/acs:create-design` is Design-phase work and normally runs
BEFORE any ticket branch exists, so it never commits to the repo's default
branch. Leave the published file in the working tree — the first Build step
(`/acs:analyze-requirements`) creates the ticket branch and commits the ticket's
docs folder, which carries this design into the branch and into the PR. If a
ticket branch for `<id>` is ALREADY the checked-out branch (a re-design
mid-ticket), commit `<design_path>` on it yourself with
`settings.formats.commit_message` and do not push — `/acs:create-pr` pushes.
A design published to the workspace partition (no docs folder, above) is
never committed.

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
`clarify.py add --skill create-design --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

- Genuinely open decision points (option choice with no objective winner, scope
  or NFR trade-offs, conflicting docs) → ask the user (AskUserQuestion or plain
  questions) BEFORE settling the decision. The scope pass's and every research
  slice's questions go into ONE grouped ask, after the research pass finishes. Present the options with their
  trade-offs; record the answer and carry it into design.md's rationale.
- Do NOT ask about researchable facts — read the code/docs instead.
- If you genuinely cannot reach the user (e.g. a non-interactive run): do not
  guess. Write result.json with `"status": "interrupted"`,
  `"stop_reason": "needs_input"` and the open decision in `summary` (there is
  no `handed_off` status and no `handoff_summary` field in a result document —
  the post-hook refuses both), run the Finish steps, and return as your FINAL
  message only:

  ```xml
  <handoff skill="create-design" ticket-id="SHOP-123" status="needs_input">
    <summary>Design blocked on user decision: sync vs. async export pipeline. Options and trade-offs drafted in design.md (Options considered).</summary>
    <artifacts><file>/abs/workspace/repo/SHOP-123/steps/create-design/design.md</file></artifacts>
    <questions><question>Should export run synchronously in-request (simpler, blocks UX >2s) or via a queued worker (new component, resilient)?</question></questions>
    <next-step>Answer, then re-run /acs:create-design SHOP-123</next-step>
  </handoff>
  ```

## Context pressure

If your context is running low mid-run: flush in-flight work and soft context
(user answers, decisions, partial findings, gotchas) to
`steps/create-design/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <id> --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop. Do not burn the
last of your context on work that would be lost.

## Finish

MANDATORY final step — never skipped, including on failure or handoff:

1. Write `steps/create-design/result.json` per the result-document
   contract in INTERNALS.md. Canonical `states` keys (EXACT names) on success:

   ```json
   {
     "status": "completed",
     "summary": "design reviewer passed with zero findings on iteration 2",
     "states": {
       "design_path": "docs/tickets/SHOP-123/design.md",
       "decision": "Queue-backed export worker behind the existing API gateway (Option B)"
     },
     "findings": [],
     "errors": []
   }
   ```

   `design_path` is the PUBLISHED path this run resolved (`<design_path>` —
   repo-relative inside the docs tree, or `"design.md"` when it was published
   to the partition); `decision` is the one-line decision statement from "Decision &
   rationale". On `failed`: keep whatever is true (e.g. `design_path` when a
   draft exists but was never published, naming the draft), put the design reviewer's
   blocking findings in `findings`, and the reason in `summary`.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-design.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — the /acs:code gate
   stays closed until it succeeds.

3. Report:
   - Direct invocation: a compact summary — decision (one line), options
     considered, conformance vs. required architecture changes, iterations used,
     and the next step: for a non-epic ticket, `/acs:code <id>`; for an epic,
     break it down into child tickets with `/acs:create-ticket <id>` (epic
     fan-out), then run `/acs:code` on a child, each of which inherits this
     design.
   - Under /acs:ship: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` <=1KB, `<artifacts>` referencing
     `<design_path>`, and exactly one `<next-step>`: `/acs:code <id>`
     for a non-epic ticket; for an epic, `/acs:create-ticket <id>` (epic
     fan-out), then `/acs:code` on a child.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-design · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: `design.md` (the published `<design_path>`); the decision in one line; architecture changes required (or "conforms")
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:code <ticket-id>` for a non-epic ticket; for an epic,
  `/acs:create-ticket <ticket-id>` (epic fan-out), then `/acs:code` on a
  child
```
