---
name: create-api-contract
description: Design a feature's API low-level design — one living document per interface (a REST resource, a CLI command group, an event topic, a gRPC service, a webhook) under lld/<feature>/api/, each operation's request/response or payload shapes, error codes, compatibility and examples traced to the acceptance criteria — each versioned, checked against the interfaces in code for design gaps, and reviewed against the HLD's integration map and API conventions, plus a per-run record api-contract.md linking every interface at its version. Takes a ticket (an epic too), a PRD feature slug, a prompt or documents — or a mix. Use in the Design phase, before or without an implementation plan, whenever a ticket or a feature adds or changes an interface, or when asked to design, spec out or document the shapes, flags, exit or error codes, or payloads of an endpoint, command, webhook, event or RPC; it writes documents only, never OpenAPI, JSON Schema, proto or other machine-readable files and never code. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell: it locates all of them itself.
argument-hint: "[ticket-id] [feature-slug] [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-api-contract. You produce one change's
**API low-level design** — the interfaces of the PRD features its requirements
trace to, one living document per interface under
`<architecture_dir>/lld/<feature>/api/`, plus the per-run record
`api-contract.md` that summarises the change — before implementation
(ADR-0134, ADR-0118, ADR-0120). This is Design-phase work run by the SA / Tech
Lead, beside /acs:create-data-design and /acs:create-flows; no plan is needed
and none is read as a boundary. Every contract item traces back to an
acceptance criterion.

**Documents only**: you and your subagents never write source code, tests or
machine-readable contracts (OpenAPI, JSON Schema, `.proto`, AsyncAPI, a GraphQL
SDL). When the repo keeps such files, `/acs:create-impl-plan` plans their
update from the approved contract and `/acs:code` writes them;
`/acs:create-test-docs` derives contract cases from it and `/acs:review-code`
checks the changeset against it. You orchestrate three subagents — the
**contract-author**, which surveys and writes, the **gap-analyst**, which
compares the existing interface documents with the code, and the
**contract-reviewer**, which judges fresh (contract-author → contract-reviewer)
— and never write a design document yourself.

This skill is independent: it never refuses because an upstream artifact is
missing — it works from what it finds (the analysis, the design, the HLD, the
code) and falls back to the run's requirements.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-api-contract --args "$ARGUMENTS"
```

`$ARGUMENTS` carries the requirements and where to put them, in any mix and
order: a ticket id (`<PREFIX>-<n>` — an epic too: Design runs on epics), a PRD
feature slug, documents (repo paths, or files attached from outside the repo —
copied into the run), and a prompt. No ticket is required: a feature slug, a
prompt or a document is enough. `step start` turns them into the run's
requirements.

If it exits non-zero: stop immediately and surface its stderr to the user
verbatim. Do not improvise a workaround. Otherwise parse the context JSON; the
fields you need: `partition`, `run_id`, `requirements` (`{path, sources,
acceptance_criteria, features, feature, needs_design}` — **Requirements:
`context.requirements` / `acs.py requirements show` — a ticket id, documents
and a prompt are only where they came from; never read ticket.json for
acceptance criteria**; its `acceptance_criteria`, `AC-1…`, are what every item
traces to), `ticket` and `ticket_id` (present only when a ticket is one of the
sources), `settings` (`design.lld_types`, `parallel.max_agents`, `models`),
`agents` (the agent name to spawn per role; each role's model and effort come
from `settings.models.create-api-contract.<role>`, inheriting when unset),
`reconcile`, `handoff_summary`, `checkout_root`. `<partition>` below is
`partition`, `<id>` is `ticket_id` when the run has a ticket, else `run_id`.

Then, in order:

1. **Type.** This skill owns one LLD type, `api-contract`. Only when
   `settings.design.lld_types` enables it is anything written; a disabled type
   is never written. Disabled → write result.json `completed` with `outcome:
   type_disabled`, summary "the api-contract type is not enabled in
   design.lld_types", `states` holding empty lists and zero counts, run Finish,
   and stop.
2. **Architecture set.** Ask acs where it is — `python3
   "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs where --doc
   living:architecture` (a `docs.architecture_dir` setting, else the folder
   holding `hld/tech-stack.md`, else an existing `docs/architecture/`): its
   `path` is `<architecture_dir>`. The interface documents are living
   documents, always shared, but acs never creates a new docs folder without
   asking (ADR-0132): when `needs` names `location` (`location_source:
   default`), the folder is a question in the ONE grouped ask below — use
   `proposed_path` or give another repo-relative folder — saved with `acs.py
   docs decide --location architecture=<folder>`; nothing is written there
   before it.
3. **The run record.** Resolve `<contract_path>` and whether it is shared —
   read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/run-record.md`.
4. **Features** — the PRD feature slugs (ADR-0120) this run designs, taken from
   the first of these that names any:
   1. **the argument** — a token of `$ARGUMENTS` that is a feature slug
      (lowercase kebab-case naming a `<prd_dir>/features/<slug>/` folder, an
      `<architecture_dir>/lld/<slug>/` folder or a PRD feature; it is otherwise
      prompt text in `requirements.md`). On a ticket run the slug must be one
      of the ticket's features (one it does not carry → stop and say so);
   2. **the requirements** — `requirements.feature`, else `requirements.features`;
   3. **the ticket** — `context.ticket.features`, when the run has a ticket.

   None → propose slugs, each made with `python3
   "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" slug --text "<PRD feature name>"`,
   as a question in the ONE grouped ask below, and once confirmed record them
   on the run: `printf '{"features": [...]}' | python3
   "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" requirements refine --from -`
   (on a ticket run it patches the ticket as `ticket save` does — never call
   `ticket save` on a run with no ticket).
5. **Baseline.** `git -C <checkout_root> status --porcelain >
   <partition>/steps/create-api-contract/baseline-status.txt`, so the review
   can tell this run's changes from what was already in the tree.

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/inputs.md`
before the first spawn — what you find decides how you scope the run, never
whether it runs.

## Resume & reconcile

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/not-a-first-run.md`
when `context.reconcile` or `context.handoff_summary` is set — verify recorded
progress against reality, then resume.

## Output contract

The contract-authors write ONLY these files, for each feature, under
`<checkout_root>/<architecture_dir>/lld/<feature>/`:

| File | Type | Required sections (in order) |
|------|------|------------------------------|
| `api/<interface>.md` — one per interface | `api-contract` | Scope; Surface; Error model; Compatibility & versioning; Examples; Traceability |

An **interface** is one unit a consumer integrates with: a REST resource or
API, a CLI command group, an event topic or stream, a gRPC service, a webhook,
a library's public module. `<interface>` is its slug (`customers`,
`order-events`, `export-cli`); an existing `api/` document keeps its name and
is revised in place. `## Surface` carries one `### ` subsection per operation,
command, message or signature (an **item**); what each holds is defined in
`create-api-contract-contract-author.md`. The first skill to touch a feature
also creates `lld/<feature>/README.md` (the PRD feature it designs, the HLD
containers it spans, a ticket history table) if absent, adds this ticket (or,
with no ticket, this run's id) to its history, and adds the feature's row to
`lld/README.md` if missing. Nothing else in the repo is written — never
`data/` or `flows/`, never `hld/`, never a machine-readable contract file.

**Design versions (ADR-0122).** Every interface document carries version front
matter set only through `acs.py design`: a new file `design init --status
<proposed|implemented> --ticket <id> --feature <slug>` (`implemented` when it
documents the interface as built, `proposed` when it designs ahead of it); a
changed file `design bump --ticket <id>`. On a run with no ticket drop
`--ticket <id>`. Items designed but not built are marked `(planned)` in their
`### ` heading. The README files are indexes, not designs: no version front
matter.

The **run record** (`<contract_path>`, Start step 3) is what this change did to
the interfaces: front matter (`ticket`, `items`, `interfaces`), then the five
headings below, linking every interface document at the version this run
left it at:

```markdown
---
ticket: SHOP-123
items: 3
interfaces: ["docs/architecture/lld/bulk-import/api/imports.md"]
---

# API contract — SHOP-123: Accept CSV imports over 10 MB

## Scope & sources
## Interfaces
## Compatibility & versioning
## Traceability
## Gaps
```

`items` is the number of `### ` subsections under `## Surface` across the
interface documents this run wrote or changed; `interfaces` lists those
documents, repo-relative.

## Reflection loop — contract-author → contract-reviewer

Max 3 iterations — a fixed **3** on every run, no path-driven verify depth;
one iteration is one write → review round (iteration 1's survey belongs to
iteration 1). Decomposition is YOURS alone — subagents never spawn subagents.

| Role | Kind | Agent | Spawn as |
|------|------|-------|----------|
| contract-author | write | `acs:create-api-contract-contract-author` | `context.agents.contract-author` |
| gap-analyst | survey | `acs:create-api-contract-gap-analyst` | `context.agents.gap-analyst` |
| contract-reviewer | judge | `acs:create-api-contract-contract-reviewer` | `context.agents.contract-reviewer` |

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/messaging.md`
before the first spawn — the `<task>`/`<result>` rules, snapshots, agent
names, the fan-out cap and the `notes merge` join.

### 1. Survey and gap analysis — iteration 1, one message

ONE contract-author, `slice="survey"`, reads the inputs and the interfaces in
code and records in `iter-1/authoring.md`: the **Interface inventory** (each
interface the requirements' acceptance criteria touch — its kind, its existing
`api/` document or "new", the code that implements it today with `path:line`,
the HLD `integration-map.md` row it details), the **Item list** (per
interface, every operation, command, message or signature the criteria add,
change or remove, NEW / CHANGED / REMOVED, today's shape from the code), the
**Conventions** (versioning, error envelope, naming, pagination, auth, from
`hld/cross-cutting.md` and the code), the compatibility questions and the open
decisions. It writes no document and reports `iter-1/contract-author-survey.json`.
Read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/contract-author.md`
when you task a contract-author — each pass's objective and early exits.

In the SAME message as the survey, when the feature already has `api/`
documents, spawn one gap analyst per existing interface document (slice id =
its file stem), its `<inputs>` that document and the feature's `data/`
documents — counted against the same cap. No such documents yet → skip the
gap analysis and say so in the report (the survey's inventory documents the
interfaces as built). Join the gap slices into `iter-1/gaps.md`. Gaps are
handled by default as: **undocumented** → documented as built;
**unimplemented** → kept and marked planned; **drifted** → a question in the
grouped ask, both readings cited.

### 2. The grouped ask

Collect the survey's questions, every drifted gap, the feature slugs when no
argument, requirement or ticket named one, the architecture folder and the run
record's share questions when `docs where` named them, and the open design
decisions; de-duplicate them and ask in ONE grouped interaction (User
interaction). The recorded `C-<n>` answers go to every writer in `<context>`.

### 3. Write — one contract-author per interface

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/writer-slices.md`
before the write — one contract-author per interface when the survey found two
or more, an integration pass on the seams between them, then the join of the
run-record fragments into the draft `steps/create-api-contract/api-contract.md`.
One interface → ONE contract-author, `slice="write"`, writes it un-sliced.

Each writer writes its interface documents in place under
`lld/<feature>/api/`, versioned as above, and its fragment of the run record
in the partition. On iterations 2-3 the writers re-run with the findings
verbatim in `<context>`, recording them under `## Findings addressed` in
their notes, and fix every finding and nothing else.

### 4. Review — reviewer slices plus the $0 checks, one turn

Read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/reviewer-slices.md`
before every review — three slices (`surface`, `trace`, `form`) in ONE
message, each with the survey notes, the writers' notes, `iter-1/gaps.md`, the
baseline status file, every written interface document and the draft in
`<inputs>`; de-duplication; the pass rule. Join them in the table's order:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-api-contract/iter-<n>/contract-reviewer.md \
  <partition>/steps/create-api-contract/iter-<n>/contract-reviewer-surface.md \
  <partition>/steps/create-api-contract/iter-<n>/contract-reviewer-trace.md \
  <partition>/steps/create-api-contract/iter-<n>/contract-reviewer-form.md
```

In the same turn, run the $0 checks yourself — they need no review result, so
they never wait for one:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check <every written interface document>
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/mermaid_lint.py" <every written interface document>
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py" \
  --sections "Scope; Surface; Error model; Compatibility & versioning; Examples; Traceability" \
  --ordered <each written interface document>

python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/front_matter_check.py" \
  --require "ticket: str; items: int; interfaces: list" \
  --ticket <id> "steps/create-api-contract/api-contract.md"
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py" \
  --sections "Scope & sources; Interfaces; Compatibility & versioning; Traceability; Gaps" \
  --ordered "steps/create-api-contract/api-contract.md"
```

Each problem `design check` reports, each lint or checker stderr line, and an
exit 2 are blocking findings of THIS iteration, appended under `##
Deterministic checks` in the joined report — remediated by the next writer
iteration, never patched by you.

**Pass rule.** The iteration passes only when EVERY reviewer slice returned
`status="completed"` with zero blocking findings and every $0 check is clean.
`status="completed"` means the review RAN; the empty `<findings>` is the pass.
On findings: persist, then AUTOMATICALLY re-run the writers with every
finding. After iteration 3 with findings remaining: stop with final status
`"failed"`, findings recorded, and no published run record — the interface
documents stay as written (status `proposed`), so say so in `summary`.

### 5. Publish the run record — the coordinator is its only writer

Once the review passes and the checks are clean, publish the draft. **The
coordinator performs this step itself, never a subagent:** the file-map write
guard (`acs_lib/filemap.py`) treats the run's Design folder as a control input
the implementers of `/acs:code` are later checked against. Copy, never
re-author:

```bash
cp "<partition>/steps/create-api-contract/api-contract.md" "<contract_path>"
```

The partition draft is workspace state and never enters the repo.

## Delivery

This skill never creates, switches or names a branch, and never stages,
commits or pushes (ADR-0127): every file it wrote stays an uncommitted change
on whatever is checked out. Record EVERY written path, repo-relative, in
result `states.files` — the interface documents, the README files and the run
record when shared (never a record kept local). `/acs:create-pr` commits them
as the change's `design` layer when the change goes to a PR; otherwise the
user reviews and commits them. End by listing those files as local changes.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them in ONE grouped interaction (a
single AskUserQuestion containing all open questions as a numbered list), not
serial round-trips. Record each answer as its own `clarify.py add` entry (one
`C-<n>` per question, `--source` preserved). Never skip a question, merge two
questions into one entry, or auto-answer outside the existing
`--source assumption --rationale "..."` rule. Record every Q&A — obtained
interactively or relayed in the prompt — with
`clarify.py add --skill create-api-contract --question "..." --answer "..."`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`.

The questions this skill actually raises are compatibility questions, and they
are user decisions, not researchable facts: whether an existing consumer may be
broken, whether the change is versioned or in-place, how long a deprecated
field is kept, which error code an existing client already depends on, which
of two shapes the product wants. Ask before specifying; a contract that
guesses a breaking change is worse than no contract. A survey that finds no
interface the requirements touch is a question too ("which interface does this
change?"), never an empty contract. Do not ask about what the requirements,
the docs or the code already answer.

If you genuinely cannot reach the user (a non-interactive run): do not guess.
Record the outgoing questions as `open` (`clarify.py add` without `--answer`),
write the result document with `"status": "interrupted"` and `"stop_reason":
"needs_input"` (`needs_input` is a stop reason, not a status), run the Finish
steps, and return a `<handoff skill="create-api-contract" ticket-id="<id>"
status="needs_input">` whose `<questions>` carry them.

## Context pressure

If your context is running low mid-run: leave the interface documents written
so far in the working tree, flush in-flight state plus soft context
(decisions, settled items, gotchas) to
`steps/create-api-contract/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, also on failure:

1. Write `steps/create-api-contract/result.json` per the result-document
   contract in INTERNALS.md:

   ```json
   {
     "status": "completed",
     "outcome": "contract_written",
     "summary": "imports API designed for bulk-import; review passed on iteration 2; run record shared",
     "states": {
       "contract_path": "docs/architecture/lld/bulk-import/SHOP-123/api-contract.md",
       "feature": ["bulk-import"],
       "files": ["docs/architecture/lld/bulk-import/README.md", "docs/architecture/lld/bulk-import/api/imports.md", "docs/architecture/lld/bulk-import/SHOP-123/api-contract.md"],
       "types": ["api-contract"],
       "interfaces": ["docs/architecture/lld/bulk-import/api/imports.md"],
       "items": 3,
       "traced_acs": ["AC-1", "AC-2", "AC-4"],
       "gaps": {"undocumented": 1, "unimplemented": 0, "drifted": 0}
     },
     "findings": [],
     "errors": []
   }
   ```

   Read `${CLAUDE_PLUGIN_ROOT}/skills/create-api-contract/references/result-states.md`
   as you write it — the canonical `states` keys and when each `outcome`
   applies. On handoff you write no result document: `handoff.py` finalizes
   the step.

2. Run the post-hook:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-api-contract.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — the run is not closed
   until it succeeds.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your
final message is the `<handoff>` XML instead — this report is for direct
invocations:

```markdown
## /acs:create-api-contract · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: interface documents written under `<architecture_dir>/lld/<feature>/api/` (each with its version and status); items specified; acceptance criteria traced; compatibility verdict and what was decided; gaps by kind; the run record and where it went (shared / kept local, whose default); documents only — no machine-readable contract file or code written; left as local uncommitted changes (`states.files`)
- **Findings**: <open findings / clarifications / assumptions, or "none">
- **Artifacts**: <repo paths written, partition phase artifacts>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:create-data-design` / `/acs:create-flows <ticket-id or feature-slug>` when the feature's data or flows need designing; then `/acs:analyze-requirements <ticket-id>` and `/acs:create-impl-plan <ticket-id>` — the plan adds the items that create or update the repo's machine-readable contract files from this contract when it keeps them; `/acs:create-pr` commits the listed files, or review and commit them yourself
```
