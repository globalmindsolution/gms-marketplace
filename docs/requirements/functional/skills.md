# Skill Requirements

Thirty skills in total. There is no registry file listing them: a skill is
a **directory** under `plugins/acs/skills/` holding a `SKILL.md`, and that is the
whole of what makes it a skill (§2.4). `skills/<name>/acs.yaml` declares what
each one reads and writes; nothing declares which group it belongs to, because
nothing needs to.

The groups below are a reader's aid, not a structure the code knows about:

- **Product & design** — `/acs:create-prd`, `/acs:create-requirements`,
  `/acs:create-architecture`, `/acs:create-docs` (the four product doc sets,
  one skill since ADR-0094), `/acs:create-project`,
  `/acs:standardize-project`, `/acs:project`, `/acs:create-ticket`,
  `/acs:create-design`.
- **Implementation** — `/acs:analyze-requirements`,
  `/acs:create-impl-plan`, `/acs:create-api-contract`,
  `/acs:create-test-docs`, `/acs:code` and its four delivery-path legs,
  `/acs:review-code`, `/acs:docs-sync`.
- **Test** — `/acs:create-e2e-tests`, `/acs:run-e2e-tests`.
- **Ship** — `/acs:create-pr`, `/acs:merge-pr`, `/acs:release`.
- **Utility** — `/acs:setup`, `/acs:install-hooks`, `/acs:update`,
  `/acs:handoff`, `/acs:ship`.

The ORDER of the implementation skills is `workflows/ship.yaml`'s list, and
nothing else states it. A run's progress over that list is `run.json`; a
skill's own progress inside a step is `steps/<skill>/state.json`.

The phase a skill sits in is a grouping, not an order. The order the Build,
Test and Ship steps run in for a ticket is declared in
`plugins/acs/workflows/ship.yaml` ([workflow.md](workflow.md#pipeline)), and
**every skill MUST be runnable on its own** — a skill MUST NOT refuse to run
because another skill has not run ([hooks.md](hooks.md)).

Seventeen of the twenty-five are **hooked** (a pre-hook and a post-hook
each): the eight Design-phase skills except `/acs:project`, all six
Build-phase skills, `/create-e2e-tests`, `/create-pr` and `/merge-pr`. The
the rest (`/setup`, `/ship`, `/handoff`, `/update`, `/install-hooks`,
`/acs:release`, `/acs:project`) are unhooked and take
no position in a run. `/run-e2e-tests` is a hooked step like any other; the
`/acs:test` alias is removed.

Every **workflow** skill MUST:

- Nine **workflow/product skills** (docs-sync, code, create-prd,
  create-design, create-architecture, create-project, create-docs,
  standardize-project, create-requirements) run the Reflection cycle with
  their own `<skill>-executor` and `<skill>-verifier` subagents — and no
  `<skill>-planner`: no skill has a plan phase (ADR-0092;
  [reflection.md](reflection.md)). Three
  **apply-work skills** (create-pr, merge-pr, create-ticket) run **inline**
  per MAR-55 invariant (b): the coordinator, optionally delegating to at
  most one executor subagent, performs the apply-work directly — no
  verifier subagent, on every delivery path. The skills-independence refactor moved
  `/code`'s plan phase out into `/create-impl-plan` and added five
  Build/Test skills (analyze-requirements, create-impl-plan, create-api-contract,
  create-test-docs, create-e2e-tests); ADR-0092 then retired the planner
  role everywhere: the twelve **authoring skills** (the nine above minus
  `code` and `create-docs`, plus those five) run **execute → verify** with an
  executor that surveys first and records its survey in `iter-<n>-authoring.md`
  (`create-docs` took that shape first, ADR-0094, because its deliverable is a
  template-bootstrapped document; the other twelve followed in ADR-0092's
  stage 2), and `code` runs execute → verify against the plan
  `/create-impl-plan` approved. Fourteen hooked skills therefore run the
  execute → verify cycle today.
- have its inputs checked by a pre-hook and its outcome persisted by a
  post-hook ([hooks.md](hooks.md)) — neither hook enforces pipeline order;
- write state **only** inside `<workspace>/<repo>/<ticket-id>/`, and write
  the ticket's human-facing documents only under the fixed
  `docs/tickets/<ticket-id>/` (the consumer repo is
  otherwise touched only where the skill's job requires it, e.g. `/code`
  edits source files);
- read configuration from the `.acs` `settings.json`
  ([configuration.md](configuration.md)), and spawn its
  executor/verifier on the models and effort levels configured there
  ([configuration.md](configuration.md#subagent-models)) (applies to the fourteen
  reflection-loop skills only — apply-work skills run inline);
- (except `/create-ticket`) resolve the target `<ticket-id>` before doing
  anything — explicit argument, else session context, else branch name
  ([workflow.md](workflow.md#ticket-context));
- record every requirement Q&A in the per-ticket **clarification ledger**
  (`clarifications.json`): research first, ask once at the cheapest phase
  (re-asking an answered question is a defect), record answers before acting
  on them, and record unanswerable decisions as visible **assumptions** with
  rationale ([workspace-and-state.md](workspace-and-state.md)); when ≥2
  clarifications are open, present all of them to the user in ONE grouped
  interaction (e.g. a single AskUserQuestion with a numbered list) — not
  serial round-trips; record each answer as its own `clarify.py add` entry
  (one `C-<n>` per question, `--source` preserved); never skip, merge, or
  auto-answer a question outside the `--source assumption --rationale "..."`
  rule (MAR-61 AC-7);
- end every direct invocation with the **standard completion report**
  (Ticket / Status / Results / Findings / Artifacts / Metrics / Next), rendered
  only after the post-hook succeeded; under `/ship` the compact XML handoff
  replaces it.

`/create-design` remains bound by every clause above despite MAR-77's split of
`acs_lib.PLANNING_SKILLS` out of `acs_lib.WORKFLOW_SKILLS`: it keeps the same
hooked lifecycle — pre-hook gate and post-hook persistence, partition-scoped
state, settings-driven subagent models, the per-ticket clarification ledger,
and the standard completion report. MAR-77 changed only where `/create-design`
sits in `acs_lib.HOOKED_SKILLS`'s internal grouping and in the pipeline order
table; none of its runtime obligations changed.

---

## `/setup` (bootstrap)

Purpose: make the `acs` plugin work on any consumer repo by configuring its
conventions and the CI that enforces them — nothing else. Every other setting
(coverage target, merge strategy, tracker, models, suites, advisories) keeps a
working default and is edited by hand in `.acs/settings.json`, validated
against `settings.schema.json`.

- MUST write only the project settings file (`<repo>/.acs/settings.json`,
  committed — conventions are the team's); there is no scope question. MUST
  NOT write a value equal to its built-in default, and MUST remove one an
  earlier run wrote, so the file carries only choices.
- The workspace derives silently to `<main-checkout>/.acs/state-machine` —
  no prompt, no required input, and no override (ADR-0086,
  [ADR-0102](../../adr/0102-documents-are-found-not-configured.md)).
- MUST prompt for **`ticket_prefix`**, suggesting one derived from the
  repo/product name (e.g. `SHOP`) — ticket ids are per-repo; there is no
  global default prefix.
- MUST show the three conventions — `formats.branch_name`,
  `formats.commit_message`, `formats.pr_title` — with their built-in
  defaults, and ask whether to keep or customize them.
- MUST offer each CI gate explicitly, never installing one silently: the
  convention check, the tests + coverage gate (which needs `tests.command`),
  and the e2e merge gate — the last offered only when `e2e`/`suites.e2e` is
  already configured. When a gate is installed, SHOULD then offer the
  one-time branch protection and labels (on admin rights and consent;
  otherwise print the command once and continue).
- SHOULD create the workspace folder if it does not exist, and verify it is
  writable.
- MUST ensure the derived in-repo state root is ignored by git through two
  layers — a tracked `.gitignore` entry and an idempotent
  `<git-common-dir>/info/exclude` append — MUST verify the combined result
  with `git check-ignore -v`, and MUST warn (never silently proceed) when
  the ignore is not actually in effect, or when a broad `.acs/` rule would
  also hide `.acs/settings.json`/`.acs/ci/*` from CI (ADR-0086).
- MUST name every retired settings key (ADR-0102) still in a settings file
  and say it is ignored. When that key is a `workspace_path` pointing at an
  external workspace left by an older acs, SHOULD offer a user-confirmed,
  one-shot migration into the in-repo state root (`migrate_workspace.py`);
  declining leaves the old workspace untouched — acs no longer reads it
  (ADR-0086).
- `/setup` is not part of the gated pipeline (no executor/verifier
  subagents); it is a simple setup skill.
- All other skills' pre-hooks fail fast (exit 2) with a "run /setup first"
  message when no `settings.json` can be found.
- Re-running `/setup` on an initialized repo **updates the existing settings
  in place** (preserving keys it does not touch) and refreshes the CI copies.
- MUST NOT write into the repo's `CLAUDE.md` (the repo's own project
  instructions) or into the user's Claude Code settings.

## `/ship` (umbrella)

Purpose: drive the declared pipeline for one existing ticket, from one
command.

- `/ship <ticket-id>` takes a **ticket id only**. A non-id argument MUST be
  refused with a pointer at the Design phase ("ship takes a ticket id; run
  /acs:create-ticket \"<prompt>\" and then /acs:ship <id>"); an epic id MUST
  be refused with the design-and-fan-out pointer. There is no
  create-a-ticket-from-a-prompt entry path.
- `/ship` MUST NOT hard-code the step order. It MUST derive every step from
  the resolved workflow file — `<repo>/.acs/workflows/ship.yaml` when the
  consumer ships one, else the plugin default — by looping over
  `acs.py run next` until it reports the list is done
  ([workflow.md](workflow.md#umbrella-command-ship)).
- It invokes the ONE step `run next` names. There is no parallel mode:
  `ship.yaml` v3 rejects `max_parallel` and `exclusive`, and what the
  parallel mode bought — not paying for a step with nothing to do — is bought
  instead by the evidenced no-op, which costs no tokens and no worktree.
- MUST stop before `/merge-pr` (which may not appear in a workflow file at
  all), and MUST NOT bypass any pre/post hook; it adds orchestration only. It
  stops because `create-pr` is the last name in the list, not because of a
  `stop_after` key.
- SHOULD be resumable: re-running it for a ticket re-derives the cursor — the
  first step in workflow order that is not `completed` — and continues from
  it. The cursor is never stored, so it cannot disagree with the ledger.
- MUST NOT stop mid-pipeline by design. The `full_verify_stop` boundary is
  removed: it existed to pre-empt a context limit the run can simply record.
  A session that runs out of context ends the in-flight step `interrupted`
  with `stop_reason: context_pressure`, and the next `/acs:ship <ticket-id>`
  resumes from the derived cursor.
- MUST re-enter `code` when `/acs:review-code` records blocking findings —
  the workflow's single `loops:` entry, at most `max_iterations` (3) rounds;
  a further round MUST fail the run rather than pass it with findings.
- No executor/verifier of its own; each step skill is **invoked
  directly by the ship coordinator in its own context** and runs its own
  reflection cycle, returning only a compact handoff — `/ship` reads the
  derived cursor rather than a stored position, so its context can be cleared
  between steps ([workflow.md](workflow.md#context-handoff-between-steps)).

## `/handoff` (utility)

Purpose: deliberately hand the current ticket/skill off to a fresh session
when the current one grows long
([workflow.md](workflow.md#session-handoff)).

- Flushes all in-flight work and soft context (user clarifications,
  decisions, partial findings, gotchas) to the run, finalizes the in-flight
  step `interrupted` with `stop_reason: context_pressure` plus a handoff
  summary, and releases the run's lock.
- Prints the exact command to continue in a new session (e.g.
  `/code SHOP-123`).
- Not part of the gated pipeline; no executor/verifier subagents.
- Workflow coordinators SHOULD trigger the same flush proactively on context
  pressure, without waiting for the user to invoke `/handoff`.

## `/update` (utility)

Purpose: assist the plugin upgrade — Claude Code owns the plugin lifecycle;
this skill owns the workflow around it.

- **User-invoked only** (`disable-model-invocation`): updating changes the
  running environment.
- Compares the installed version (`plugin.json` at the install root) with the
  latest release; summarizes the CHANGELOG delta between them and calls out
  breaking changes (MAJOR bumps, settings-key changes, state-shape notes).
- With user consent, refreshes the marketplace
  (`claude plugin marketplace update gms-marketplace`) — updates reach consumers only
  when the plugin's `version` bumps (semver; automated release tagging).
- Runs post-update migration checks: settings valid against the new schema,
  no leftover `statusLine` / `subagentStatusLine` setting still pointing at an
  acs status-line script (acs no longer ships them —
  [ADR 0103](../../adr/0103-no-status-line-no-cost-metering.md); the fix is
  removing that setting), workspace reachable.
- Reloading is the user's action (`/reload-plugins` or a new session); the
  skill states this explicitly — the current session keeps the old version.
- Not part of the gated pipeline; no executor/verifier subagents.

## /acs:run-e2e-tests (test)

Purpose: the standing, schedulable **suite runner** over the `suites`
settings map — runs the product's configured test commands (unit,
integration, e2e, regression, or any other named suite) and reports results,
closing the loop on failures with a regression ticket.

- **Model-invocable** (it does not set `disable-model-invocation`): a
  natural-language request to run the configured test suites, run a named
  suite, or check whether anything broke routes here.
- **Argument contract:** no `--suite` flag runs every suite in `suites`; one
  or more `--suite <name>` flags run only the named subset.
- **Unhooked** — like `/setup`/`/update`,
  `/acs:run-e2e-tests` has no executor/verifier pair, no pre- or
  post-hook, and no skill-start ticket allocation.
- **`/acs:test` is removed, not deprecated.** The alias that was to survive
  one release goes with the rename instead, because the surface it aliased
  was never released; `/acs:run-e2e-tests` is the skill and no ledger key
  named `test` is accepted.
- **Not read-only**: every run writes a results
  artifact to the workspace, and a failure path can mint or comment-bump a
  ticket.
- **It is a hooked step like any other.** `pre-run-e2e-tests.py` gates it on
  its inputs and `post-run-e2e-tests.py` records the step, so it no longer
  writes its own ledger entry through a side channel. The step's status is
  what the derived cursor reads to decide whether the pipeline has passed it;
  it opens or shuts no gate, because no gate depends on it. When there is no
  suite configured and nothing owed, the pre-hook records an evidenced no-op
  from the plan's `## Contract` block rather than running.
- **All-green determinism:** when every suite passes, the run makes zero
  model calls and mints no tickets — triage only runs on the failure path.
- **Failure-path triage:** on a failing suite, the skill derives a stable
  regression key and applies a three-way policy — mint a new ticket, comment-
  bump an existing open one, or open a new ticket linked to a closed one that
  recurred — never duplicating and never silently reopening a closed ticket.
  See `docs/adr/0044-acs-test-closed-loop-ticketing.md` for the full policy.
- **Scheduling is the caller's job** — Claude Code routines/cron invoke
  `/acs:run-e2e-tests` headless; the concrete recipe lives in
  `templates/operations/test-scheduling.md` (shipped by `/acs:create-docs operations`),
  not duplicated here.
- **Ticket-scoped mode (`--for-ticket <id>`):** reuses the same
  suite-execution core (Steps 1-3: setup→command→teardown, the
  results-artifact write) scoped to the reserved `e2e` suite plus the
  ticket's own suites — read from `test-cases.md` when the ticket has one,
  falling back to the folded Test-plan section — but skips the
  regression-ticket triage/mint-or-bump loop entirely and instead returns a
  `{status, failure_output}` verdict. It is the `run-e2e-tests` step of
  `ship.yaml`. A failure ends the step `failed` and stops the run for a
  human: `on_fail` and its `relay_to`/`max_loops` bound are removed with the
  rest of the workflow language (ADR-0096), and the one loop the workflow
  declares is `review-code` → `code`. See
  `docs/adr/0068-acs-test-ticket-scoped-fix-and-retest-mode.md`.

## /acs:release (utility)

Purpose: the one-command **release-cut** utility — assembles/verifies the
CHANGELOG section for a release version from the merged-ticket archive, and,
for tickets merged without an archive entry, from `base_branch` commit
history, bumps the version-location files plus any extra refs configured in
the repo's `.acs/settings.json` `release` block, dates the section, and opens
an exempt `release/*` PR for a mandatory human merge.

- **Unhooked** — like `/setup`/`/update`,
  `/acs:release` has no executor/verifier pair, no `release-state.json`
  skill-start ticket allocation, no `.lock`, no pointer file, no partition.
  It is not part of the gated pipeline.
- **Fails fast** when no `release` block is configured in `.acs/settings.json`
  — before shelling out to `release_notes.py` at all.
- **Runs the repo's pre-release gate before the cut.** When the block
  declares `pre_release_gate`, every command runs verbatim, in order, from
  the checkout root before anything is drafted, bumped, branched or pushed;
  the first non-zero exit ends the run `failed` with nothing written, and
  nothing bypasses the step. The release PR body carries each command's exit
  code and output tail as the cut's evidence. A repo that declares no gate
  is told so and proceeds.
- **Writes no workspace artifact** — unlike `/acs:run-e2e-tests`'s
  `results.json`, the
  durable record of a release cut is the release PR itself; `workspace` is
  read-only input (to enumerate the merged-ticket archive), never a write
  target. The git-history fallback source is the repo checkout, not the
  workspace — this is user-observable: the count is non-zero even with no
  `archive/` present whenever `base_branch` history carries leading
  ticket-ref commit subjects (a tracker-ref-only history, e.g. `[#399] …`,
  still yields zero — the fallback recovers only subjects whose leading
  token is a ticket ref).
- **Never publishes itself** — it never runs `git tag` or `gh release create`;
  the privileged tag/publish step stays in the block's `publish_driver`.
- **Scope**: cutting a new version of a repo already configured for release
  cuts — not for opening a ticket's own PR (`/acs:create-pr`) or
  landing/merging a PR (`/acs:merge-pr`).
- **Enumeration provenance and prefix anchoring**: each ticket the coverage
  report and draft enumerate is stamped `source: archive|git-log`, and
  `/acs:release` passes `--ticket-prefix <settings.ticket_prefix>` to both
  `draft` and `bump` to anchor the git-history fallback to this repo's own
  ticket ids.

## Product-level delivery (tickets)

**Every change is tracked as a ticket — including product-level work.**
Tickets are the project-management record, so the three product-level
skills, while not running the ticket pipeline, MUST each create their own
**delivery ticket** per run:

- The skill creates the ticket first (type **task**, e.g.
  `SHOP-1 — Product definition (PRD)`): a normal id from the per-repo
  counter, a normal workspace partition, tracker sync when configured (so
  PRD/architecture/scaffold work is visible in Jira / GitHub Projects), and
  the standard archive lifecycle. Re-running a product-level skill (e.g. a
  PRD amendment) creates a **new ticket** for that change. Re-running
  `/create-prd` for an amendment creates a new ticket with a specific title
  (e.g. `SHOP-5 — Amend PRD: add org-level enforcement policy`) when a
  usable request is provided; without a usable request the built-in
  `"Product definition (PRD)"` title applies.
- All formats apply with the real ticket id: the skill creates the branch
  (`formats.branch_name`), commits (`formats.commit_message`), and opens
  the PR (PR formats, `ACS` label) itself — `/create-design` and `/code`
  are not involved.
- The skill's state file (`create-prd-state.json`, …) lives in the delivery
  ticket's partition like any other skill state, records the PR reference,
  and `run.json` records the run's workflow. Locking,
  resume and handoff work exactly as for any other ticket.
- `/merge-pr` works as for any other ticket: readiness check, merge, mark
  done (and sync), archive the partition.

## `/create-prd` (product-level)

Purpose: define the product — the **PRD** is the root document everything
else is verified against.

- Product-level and ticket-independent. Runs before `/create-architecture`
  (which checks for the PRD at Start). Re-running **amends the PRD in
  place**, preserving sections it does not touch.
- For a **greenfield** product: elicits the definition from the user. For
  an **existing** product: reverse-engineers a baseline PRD from the
  codebase and docs, confirming open points with the user.
- Produces the PRD doc set in the consumer repo wherever the repo already
  keeps its PRD — found through `CLAUDE.md` and the repo, not a setting
  ([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)) — else at `docs/product/`
  ([configuration.md](configuration.md#document-and-workspace-locations)):
  - `prd.md` — vision, problem statement, target users & personas, goals
    with **measurable success metrics**, prioritized features (e.g.
    MoSCoW), product-level NFRs, constraints & assumptions, out-of-scope;
  - `roadmap.md` — milestones/phases mapped to intended epics, plus a
    **"Release versions"** mapping table (each release version → its
    milestone/wave and the epic(s) it delivers).
- Reflection cycle (execute → verify, no planner — ADR-0092):
  `create-prd-executor`, `create-prd-verifier`. The verifier checks: all required sections
  present, features trace to goals, success metrics are measurable,
  nothing contradicts the stated constraints, and every roadmap milestone
  resolves to exactly one release version (0 orphan milestones) — plus a
  deterministic `structure` floor (declared `required_sections`, blocking)
  and a blocking `audience-style` check (declared audience/style profile; an
  unwaived audience-mismatch blocks, a `clarify.py --source assumption` waiver
  makes it `severity="info"`, non-blocking).
- **Independent corroboration (MAR-304).** The executor additionally records
  three sections in its authoring notes (`iter-<n>-authoring.md`) that the
  deterministic floor parses: `## Code evidence`
  (brownfield/amend only, one citation per brownfield code claim in the
  house grammar; `N/A — greenfield, no code to cite` in greenfield),
  `## Answer fidelity` (one line per `clarifications.json`
  answered/assumed entry, naming a verbatim anchor in `prd.md`/`roadmap.md`,
  or an `N/A: <why>` escape), and `## Roadmap milestones` (one line per
  declared milestone, its verbatim `roadmap.md` heading text). The
  verifier's `Plan conformance` dimension runs the shared deterministic
  `prd_conformance_check.py` floor over these three families — importing
  `citation_check.py`'s own resolution helpers unchanged for the
  code-evidence family — then itself judges the semantic ceiling: whether
  each answer is reflected and not contradicted (every `N/A` judged, never
  silently accepted), whether each resolved code citation substantiates its
  claim, and whether each matched milestone maps to the intended epic.
  Every such finding — mechanical or semantic — and an exit 2 from the
  script are `severity="blocking"`; there is no `severity="info"`
  carve-out. `clarifications.json` and the repo root are declared
  verify-task inputs/constraints for this skill.
- The executor's survey also runs the shared ADR-0012 design-time
  doc-consistency step, surfacing gap/staleness findings through the
  existing clarification ledger.
- State lives in the delivery ticket's partition
  (`create-prd-state.json`).
- Delivery: docs-only PR via the
  [product-level delivery rules](#product-level-delivery-tickets) — each
  run creates its own delivery ticket.
- Downstream: `/create-architecture` is verified against the PRD, and
  `/create-ticket` traces tickets to PRD features and flags divergence
  ([workflow.md](workflow.md#product-level-architecture)).

## `/create-architecture` (product-level)

Purpose: bootstrap and regenerate the **product architecture doc set** — the
living system documentation the whole pipeline designs and verifies against.

- Product-level and **ticket-independent**: not part of the per-ticket
  pipeline. Run once when starting a product (or onboarding `acs` onto an
  existing repo); re-run to regenerate after major shifts.
- MUST take the **PRD** as its primary input — the skill locates it at
  Start and stops when none is found: "no PRD found — run /acs:create-prd
  first (it also baselines existing products)"
  ([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)). For an
  **existing codebase** it additionally
  reverse-engineers the current architecture from the code and docs,
  confirming open points with the user; for a **greenfield** product it
  designs the system to satisfy the PRD.
- Produces the doc set in the **consumer repo** wherever the repo already
  keeps it, else at `docs/architecture/`
  ([configuration.md](configuration.md#document-and-workspace-locations)),
  split into **high-level design (HLD)** and **low-level design (LLD)**:
  - `hld/overview.md` — system context, goals, quality attributes,
    constraints;
  - `hld/c4-context.md`, `hld/c4-container.md`, `hld/c4-component.md` — the
    **C4 model, levels 1–3**; C4 level 4 (code) is deliberately out of
    scope — the code and its API docs serve that level;
  - `hld/data-model.md` — entities and relationships (ER diagrams);
  - `hld/deployment.md` — runtime and infrastructure topology;
  - `hld/tech-stack.md` — languages, frameworks, conventions;
  - `hld/project-structure.md` — the intended repo layout derived from the
    C4 container/component views, the canonical target
    `/acs:standardize-project` audits an existing repo against;
  - `lld/flows/<flow>.md` — **sequence diagrams** for the key runtime
    flows, one file per flow — bootstrapped for the main flows (selected by
    the executor's survey, confirmed with the user) and grown ticket by ticket;
  - `lld/contracts.md` — interface/API contracts between components.
- All diagrams are **Mermaid** (C4, ER, sequence, and state diagrams as
  code: diffable, reviewable, rendered by GitHub, maintainable by agents).
- Runs the Reflection cycle as execute → verify (no planner — ADR-0092) —
  `create-architecture-executor`, `create-architecture-verifier`. The
  verifier checks: the design **satisfies the PRD** (goals, product-level
  NFRs, constraints); the docs match the actual codebase; they are
  internally consistent; diagrams agree with the prose; and **HLD and LLD
  agree with each other** (every participant in a sequence diagram exists
  in the C4 views) — plus a deterministic `structure` floor over the
  prose-structured files (declared `required_sections:<file>`, blocking)
  and a blocking `audience-style` check (an unwaived audience-mismatch blocks;
  a `clarify.py --source assumption` waiver makes it `severity="info"`,
  non-blocking).
- The executor's survey also runs the shared ADR-0012 design-time
  doc-consistency step, surfacing gap/staleness findings through the
  existing clarification ledger.
- State lives in the delivery ticket's partition
  (`create-architecture-state.json`)
  ([workspace-and-state.md](workspace-and-state.md)).
- Delivery: docs-only PR via the
  [product-level delivery rules](#product-level-delivery-tickets) — each
  run creates its own delivery ticket; the TDD pipeline does not apply to a
  docs-only change.
- Maintenance afterwards belongs to the pipeline: `/create-design` designs
  against the doc set, and `/code` updates it whenever a change alters the
  architecture ([workflow.md](workflow.md#product-level-architecture)).

## `/acs:create-docs` (product-level)

Purpose: bootstrap and maintain the four **product doc sets** — `quality`
(test strategy, coverage policy), `operations` (release process, runbooks,
observability, incident response, test scheduling), `principles`
(engineering principles + rationale) and `standards` (coding standards,
conventions, review checklist) — the standing contracts the pipeline
verifies against. One skill, four sets (ADR-0094): the sets used to be four
internal leg skills that differed only in a table row, and that table,
`acs_lib.DOC_SETS`, is now the whole difference.

- Product-level and **ticket-independent**: not part of the per-ticket
  pipeline. Run once after `/acs:create-architecture`; re-run to refresh a
  set after its policy changes. Takes `all`, a comma-separated list of sets
  (`quality` or the former leg name `create-quality`), or a delivery-ticket
  id to resume one set; a token naming no set refuses the whole run.
- **Declared, not inferred**: `DOC_SETS` declares, per set, the directory a
  new set is created in when the repo has none (`docs/quality/`,
  `docs/operations/`, `docs/principles/`, `docs/standards/` — an existing
  set is found through `CLAUDE.md` and the repo, not configured,
  [ADR-0102](../../adr/0102-documents-are-found-not-configured.md)), its
  delivery-ticket title, its template
  directory, its output files with the sections each must carry (the first
  file is the sentinel that says the set has shipped), its audience
  register, its upstream inputs and its dependency edges. Adding a fifth set
  is a row plus its templates. `fanout_batches()` reads the derived view
  `DOC_BOOTSTRAP_DEPENDENCIES` (keyed by set name) and the sets the
  coordinator found already present in the repo to decide eligibility and
  batching; `parse_doc_set_arg()` is the argument contract.
- MUST take the **PRD** (its Non-functional requirements section for
  `quality` and `operations`; the PRD generally for `principles` and
  `standards`) and the full architecture set as upstream inputs —
  architecture is upstream of every set. `standards` additionally reads the
  principles set **when the repo has one** (the conformance
  chain `architecture → principles → standards`); when the set is absent
  the executor notes the grounding step as not
  applicable and proceeds — never a block. `principles` has no cross-read on
  `standards/`. That soft edge is why `principles` lands in an earlier
  fan-out batch than `standards`.
- **One precondition for every set**: the skill checks for the architecture
  doc set (its `hld/tech-stack.md`, not merely a directory) at Start and
  stops when none is found — "no architecture doc set found (expected
  hld/tech-stack.md) — run /acs:create-architecture first." — once, before
  any delivery ticket is minted ([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)).
- **One delivery ticket per set**: `acs.py step start --step create-docs
  --doc-set <set> --allocate` mints a `task` ticket titled from `DOC_SETS`
  that records its `doc_set`; each set runs in its own worktree on its own
  branch and lands as its own docs-only PR; sets run in capped parallel
  (at most `max_parallel`, default 2). Failures are isolated per set; a set
  resumes by its ticket id.
- Runs the Reflection cycle as **execute → verify, no planner** (ADR-0092
  class D): `create-docs-executor` authors the set — decides bootstrap vs
  re-run from the disk, bootstraps each file from
  `templates/<set>/` verbatim, tailors it to the detected stack (and, for
  `standards`, to the stated principles), and writes its authoring notes
  (`iter-<n>-authoring.md`: mode, Upstream inventory, ADR-0012 consistency
  findings, decisions); `create-docs-verifier` judges it fresh — doc-set
  completeness, architecture conformance (stack/technology claims agree with
  `architecture/hld/tech-stack.md`), required sections, authoring
  conformance, docs-only changeset, consistency, a deterministic `structure`
  floor over each file (declared `required_sections:<file>`, blocking) and a
  blocking `audience-style` check (an unwaived audience-mismatch blocks; a
  `clarify.py --source assumption` waiver makes it `severity="info"`,
  non-blocking). The set, its files and its sections reach both agents as
  task constraints; the same two agent files serve every set.
- **Citation corroboration (MAR-303).** The executor MUST record every
  `Upstream inventory` citation in the one-line grammar

  ```
  - <claim> — `<path>[:line]` — "<verbatim excerpt>"
  ```

  The path is backtick-quoted exactly as shown, the optional
  `:line`/`:line-start-line-end` suffix is advisory only, and the excerpt is
  verbatim and mandatory. The verifier's `authoring-conformance` dimension
  MUST independently re-open and check every such citation: it runs the
  shared deterministic `citation_check.py` floor over the located PRD +
  architecture set (plus the principles set for `standards`, when
  present), then itself judges substantiation for every
  citation the script resolves. Every such finding — mechanical or semantic —
  and an exit 2 from the script are `severity="blocking"`; there is **no**
  `severity="info"` carve-out. The located PRD is a declared verify-task
  constraint.
- The executor also runs the shared ADR-0012 design-time doc-consistency
  step, surfacing gap/staleness findings through the existing clarification
  ledger; the verifier's `consistency` dimension confirms any such findings
  were resolved or explicitly deferred.
- State lives in each set's delivery-ticket partition
  (`steps/create-docs/state.json`; the run's own `workflow` field
  with the step key `create-docs`)
  ([workspace-and-state.md](workspace-and-state.md)).
- Delivery: docs-only PR per set via the
  [product-level delivery rules](#product-level-delivery-tickets) — each
  run creates its own delivery ticket per set; the TDD pipeline does not
  apply to a docs-only change.

## `/acs:create-requirements` (product-level)

Purpose: bootstrap or amend the consumer **requirements doc set** — the
living behavioral contract, one file per feature area under `functional/`
and one file per NFR item under `non-functional/`.

- Product-level and **ticket-independent**: not part of the per-ticket
  pipeline. Run once to bootstrap a repo's requirements set, or re-run to
  amend it; either way `/acs:code`'s documentation step keeps accreting into
  the same files afterward.
- **Three modes**, classified by the executor's survey from the located
  requirements set's content and the codebase:
  - **brownfield** — reverse-engineer the set from an existing codebase
    (architecture-aware feature-area enumeration, codebase-inventory
    fallback; each requirement DRAFT / code-cited);
  - **greenfield** — elicit the definition from the user when there is no
    meaningful codebase and the set is absent (each requirement DRAFT /
    grounded in the user's answer, no code-citation expected);
  - **amend** — augment only absent/ungrounded area files on a
    substantially-populated set, preserving every existing file
    byte-for-byte.
- **Standalone but architecture-aware**: uses the architecture doc set's
  container/component views (`c4-container.md`/`c4-component.md`/
  `project-structure.md`) when present, degrades to a codebase inventory
  when absent; no hard PRD/architecture dependency (the skill checks for
  neither at Start).
- Produces the doc set in the consumer repo wherever the repo already keeps
  it, else at `docs/requirements/`
  ([configuration.md](configuration.md#document-and-workspace-locations)),
  with `functional/` and `non-functional/` subfolders — or the subfolder
  names an existing set already uses.
- Runs the Reflection cycle as execute → verify (no planner — ADR-0092) —
  `create-requirements-executor`, `create-requirements-verifier` —
  including a deterministic `structure` floor over each produced area file
  (blocking) and a blocking `audience-style` check (an unwaived
  audience-mismatch blocks; a `clarify.py --source assumption` waiver makes it
  `severity="info"`, non-blocking), plus the
  dimensions specific to this skill: coverage (≥90%, 0 silent omissions),
  citation (100%; user-answer-cited for greenfield, code-cited for
  brownfield), DRAFT-marker, no-fabrication, functional/non-functional
  routing, and augment-only-absent/no-overwrite.
- **Additive / no-overwrite**: never overwrites a human-authored area file;
  every elicited/extracted requirement is DRAFT / human-confirm-required via
  the interactive-confirm / clarify-ledger gate before write — uniform
  across all three modes (C-22).
- State lives in the delivery ticket's partition
  (`create-requirements-state.json`)
  ([workspace-and-state.md](workspace-and-state.md)).
- Delivery: docs-only PR via the
  [product-level delivery rules](#product-level-delivery-tickets) — each
  run creates its own delivery ticket; the TDD pipeline does not apply to a
  docs-only change.

## `/create-project` (product-level)

Purpose: scaffold a fresh product's repo skeleton from the approved
architecture, so the ticket pipeline works from the very first ticket.

- Product-level, ticket-independent, and **greenfield-only** — existing
  codebases never need it. Runs once, after `/create-architecture`: the
  skill checks for the architecture doc set (its `hld/tech-stack.md`) at
  Start and stops when none is found (the tech stack and structure must be
  settled before scaffolding).
- Scaffolds, per `hld/tech-stack.md` and the HLD structure:
  - directory layout matching the container/component views;
  - package/build configuration;
  - the **test framework and coverage tooling**, wired to measure
    `test_coverage_percent` — the `/code` TDD gates depend on this existing
    from ticket #1;
  - an **e2e harness** (plus one smoke e2e test and CI wiring, and a proposed
    `e2e` settings block) when the architecture has a user-facing or
    cross-component surface;
  - linter/formatter and pre-commit configuration;
  - a CI workflow running build, lint, tests, and coverage;
  - `.gitignore`, README skeleton, and a **minimal green vertical slice**
    (entrypoint + smoke test) proving the harness works.
- Reflection cycle (execute → verify, no planner — ADR-0092):
  `create-project-executor`, `create-project-verifier` — the executor pins
  the scaffold in `iter-1-authoring.md` before writing it, and the verifier
  MUST actually run build, lint,
  and tests and see them pass; a scaffold that doesn't run green fails
  verification.
- State lives in the delivery ticket's partition
  (`create-project-state.json`)
  ([workspace-and-state.md](workspace-and-state.md)).
- Delivery: bootstrap PR via the
  [product-level delivery rules](#product-level-delivery-tickets) — its own
  delivery ticket. The scaffolded CI workflow runs on this very PR —
  proving the harness green in CI, not just locally.

## `/acs:standardize-project`

Purpose: audit an EXISTING (brownfield) repo against the approved doc set
and acs-readiness tooling, then additively scaffold whatever is missing —
the brownfield counterpart to `/create-project`'s greenfield-only scaffold.

- Its own reflection-loop workflow skill with its own delivery ticket per run
  (type `task`, titled "Brownfield project standardization") — **not** a
  doc-set producer and adds no new settings key (D5 Option B);
  distinct from the product-level doc-set skills listed above.
- Needs the architecture doc set: the skill checks for its
  `hld/tech-stack.md` at Start and stops when none is found
  ([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)).
- Audits the repo's principles and standards sets (located through
  `CLAUDE.md` and the repo), `hld/project-structure.md`
  (MAR-120), and acs-readiness tooling (coverage/CI/pre-commit/e2e) against
  the repo on disk. No refusal guard on its own set — it has none; a
  missing principles or standards set gracefully degrades
  to fewer audit inputs, never a hard block.
- Scaffolds **additively only**: it may add missing docs/config/CI/tooling
  files, but never moves, renames, deletes, or rewrites existing source —
  the verifier re-runs `git diff --name-status` every iteration
  (`classify_additive_diff`) and blocks on any status outside the
  allowlist (D6).
- **e2e CI-gate scaffold (E2E-2):** when `settings.e2e`/`suites.e2e` is set and
  `.github/workflows/acs-e2e.yml` is missing, the readiness-tooling audit's e2e
  dimension becomes a concrete scaffold target — `acs-e2e.yml` + `run-e2e.py`,
  reused verbatim from `/acs:setup`'s (E2E-1) committed templates, under
  allowlist categories 1+2. An existing `acs-e2e.yml` is never overwritten; the
  gap becomes a `recommended_follow_ups` entry instead. This skill never wires branch protection itself
  — that stays with `/acs:setup`, surfaced as a `recommended_follow_ups` entry pointing there.
- Runs the Reflection cycle as execute → verify (no planner — ADR-0092) —
  `standardize-project-executor`, `standardize-project-verifier` — as two
  separate subagent contexts: iteration 1's executor audits first and
  records the audit in its authoring notes (`iter-1-authoring.md`), then
  scaffolds from them (the per-iteration re-plan went with MAR-302, the
  plan phase itself with ADR-0092). The loop body is execute → verify only,
  cap 3 on every run, counting execute+verify rounds.
- **Allowlist provenance and immutability (MAR-302).** The Additive-surface
  allowlist is authored exactly once, by the iteration-1 executor, in
  `iter-1-authoring.md`, and is frozen and authoritative for the whole run: the
  executor's writable surface is monotonically non-increasing across
  iterations 1-3 (it may shrink, e.g. via a narrowing finding, but never
  grow), and the verifier re-reads that same literal frozen path every
  iteration rather than trusting a per-iteration re-derivation. This bounds,
  and does not close, the iteration-1 trust gap (ADR-0079).
- **Out-of-scope-finding route (MAR-302).** A verifier finding whose
  remediation would need a path/category outside the frozen iteration-1
  allowlist is never silently added to the executor's writable surface. It
  degrades to `severity="info"` and is surfaced as a `recommended_follow_ups`
  entry **only** when all four of these hold (fail-closed otherwise, i.e.
  undetermined stays blocking): `dimension="plan-conformance"`; the finding
  is of the missing-scaffold/under-coverage class (never the over-scaffold
  "unplanned extra scaffold file" class); the remediation target lies
  outside the frozen allowlist; and the target is absent from this
  iteration's `git diff --name-status` output. `dimension="additive-only"`,
  `dimension="doc-set-authorship"`, `dimension="recommended-follow-ups-only"`,
  `completion-report` shape findings, and dimension 4's second clause ("no
  unplanned extra scaffold file") are **never** degradable — they always
  block (ADR-0079).
- **Executor-refusal route, class-scoped (MAR-302).** An executor refusal
  for an out-of-frozen-allowlist finding converts to a
  `recommended_follow_ups` entry **only** when the underlying verifier
  finding is of that same degradable `plan-conformance` missing-scaffold
  class, judged from the verifier's own prior finding — never from the
  executor's self-report. Every other refusal class — including an
  over-scaffold `plan-conformance` finding, or any `additive-only` /
  `doc-set-authorship` / `recommended-follow-ups-only` / `completion-report`
  shape finding — remains a genuine run failure. This is **not** an
  unconditional conversion; fail closed on any undetermined class
  (ADR-0079).
- Structural gaps outside the additive-surface allowlist are surfaced as
  `recommended_follow_ups` entries in the completion report and PR body —
  **never** auto-minted as new tickets (D7).
- State lives in the delivery ticket's partition
  (`standardize-project-state.json`)
  ([workspace-and-state.md](workspace-and-state.md)).
- Delivery: one reviewed PR on its own delivery ticket, zero source
  relocations; `/acs:merge-pr` lands it like any other ticket.

## 1. `/create-ticket`

Purpose: turn a raw user prompt into a well-formed ticket.

- MUST analyze and clarify requirements from three sources: the **user
  prompt**, the **codebase**, and existing **docs**.
- MUST consult the **PRD** when present: tickets SHOULD trace to PRD
  features/goals, and epics SHOULD derive from the roadmap. MUST also read
  the touched areas' **living requirements** files (found in the repo) as
  the current behavior and flag any contradiction the request implies
  (deliberate behavior change vs. mistake). When a requested
  capability goes beyond the PRD, `/create-ticket` MUST flag the divergence
  and propose a PRD amendment (a `/create-prd` re-run, user-confirmed)
  before proceeding.
- MUST interact with the user to resolve ambiguities before finalizing
  (clarifying questions).
- **AC/DoD substantiveness gate (standing behavior, MAR-157):** Step 1 flags
  any proposed `acceptance_criteria` entry that is not concrete/testable
  (vague satisfaction-claim boilerplate with no observable outcome, e.g.
  "works correctly"), for both root tickets and epic child fan-out. Step 2
  surfaces every flagged entry to the user; the ticket does not finalize with
  a flagged entry unless the user explicitly confirms it anyway. No new subagent
  is introduced — the check is inline coordinator judgment folded into the
  existing Step 1/Step 2 flow.
- MUST create a ticket with a type of **epic**, **story**, or **task**.
- When the ticket type is **epic**, its own creation run mints no children
  and ends with `children: []`; `/create-ticket <epic-id> --fan-out`, run
  after the epic's design is approved, mints them — the breakdown is
  derived from the design's slice/seam content when present and
  user-confirmed at the same Step-2 gate. Each child gets its own
  `<ticket-id>` and runs its own pipeline. The epic's status is
  auto-managed: **In Progress** when work starts on any child, **Done**
  when all children are merged (see
  [workflow.md](workflow.md#epic-fan-out)).
- Ticket title and description MUST follow the per-type ticket formats
  configured in `settings.json` — epic, story, and task each have their own
  title/description format ([configuration.md](configuration.md)).
- Tickets are **local-first**: the ticket JSON in the workspace is the local
  source of truth. Optionally, based on the `tracker` config in
  `settings.json`, the ticket syncs **two-way** with a **GitHub Project** or
  **Jira board**:
  - `ticket.json` MUST hold a mapping field linking the local ACS id to the
    remote key (e.g. Jira `PROJ-456`); the local `<ticket-id>` always names
    the workspace partition.
  - Tracker access goes through the official CLIs — **`gh`** for GitHub and
    **`acli`** for Jira — which handle authentication themselves.
- MUST persist the ticket (and its `<ticket-id>`) into the workspace; the
  `<ticket-id>` names the workspace partition for the whole pipeline.
- Inline shape (MAR-55 invariant (b)): the coordinator runs apply-work
  directly, optionally delegating to at most one `create-ticket-executor`
  subagent; no planner subagent; no verifier subagent. Correctness is gated by
  schema validation and the user-confirmation gate (`docs_only`, and the
  child breakdown in a `--fan-out` run), not an in-skill verifier.
- Ticket ids use the **per-repo prefix + sequence** (e.g. `SHOP-123`); the
  per-repo counter lives in `<workspace>/<repo>/counters.json`. The
  **first** allocation for a `(repo_id, prefix)` partition is fail-closed —
  it refuses with exit 2 and a confirmable local-evidence proposal rather
  than restarting the sequence at 1, and a human confirms with
  `--seed-next <n>`; an already-populated counter is treated as already
  reconciled. See `workspace-and-state.md` for the recorded fields.
- MAY **import an existing remote ticket**: `/create-ticket <remote-key>`
  (e.g. `PROJ-456`) pulls the issue from the configured tracker, creates the
  local ticket with a fresh local id and the external mapping, and then runs
  the normal analysis/clarification on the imported description — imports get
  the same clarification, typing, PRD trace, and `needs_design` decision as a
  local request (`needs_design` is set only when the imported ticket is an
  epic; story/task imports are always `false`). From there the ticket ships
  like any local one.
- Two-way sync runs **on demand** (triggered explicitly by the user or a
  skill); scheduled background sync routines are a later enhancement.
- Sync conflicts (both the local and the remote ticket changed) are resolved
  by **asking the user** which side wins.
- Ticket schema — required fields: **title, type, description, acceptance
  criteria, priority, parent epic, children, status, external mapping,
  assignee, story points, needs-design flag, docs-only flag**. Parent/child links are stored
  in **both directions** (epic lists `children`; each child stores `parent`).
- MUST set **`needs_design`**, epic-only: always `true` for epics (stated,
  not asked); always `false` for stories and tasks, never offered or
  confirmed ([workflow.md](workflow.md)).
- MUST set **`docs_only`** during analysis (coordinator-recommended, user-confirmed,
  default `false`): `true` only when the change touches no executable code or
  tests. The flag relaxes `/code`'s tests-first and coverage hard-fail — the
  full suite still runs once and must stay green, and a diff line touching
  executable code under the flag is a blocking verifier finding.
- MUST NOT classify the ticket's rigor. `/create-ticket` used to capture a
  `size` and a `stakes` axis (MAR-56) and derive a `lane` from them; ADR-0095
  retired all three. Rigor is now ONE judgement, made once, by `/ship`, from
  the implementation plan — the first artifact that says what the change
  actually is, rather than what a request sounded like before anyone read the
  code. `ticket.json` therefore carries no `size`, `stakes` or `lane` field,
  and a ticket that still has them from an older build is read as if it did
  not (`docs/adr/0095-static-delivery-path-routing.md`).
- MUST size stories/tasks to **one reviewable PR** (rule of thumb ~<=400
  changed lines, one concern, grounded in a codebase survey); above the bar the
  coordinator recommends an epic with children cut at PR-sized, independently
  shippable seams.
- MAY **split an existing oversized ticket** (`/create-ticket split <id> ...`,
  invoked directly with a split request): the ticket becomes an epic
  **keeping its id**, description, and PRD trace; children are minted at the
  recorded seams; downstream work already present requires user confirmation
  first.
- **GitHub-native reconciliation (standing behavior, MAR-75):** on GitHub
  tracker sync (Step 5) the synced issue carries the acs ticket id on its body
  (`acs-ticket: {ticket_id}`, rendered by the type description templates) and
  is filled with every field the target Project schema supports — the `ACS`
  and type labels, the assignee when known, the milestone when the repo uses
  one, and applicable Project fields (Status, Type); a field the schema does
  not define is surfaced, not silently skipped. `local` (unsynced) tickets are
  unaffected.
- **Fan-out tracker sync (standing behavior, MAR-84):** the tracker-sync set
  Step 5 syncs is the root ticket (unless it is an import) plus **every child
  minted during epic fan-out** (Step 4) — no fanned-out child is left
  unsynced — **EXCLUDING any ticket whose `external` is already non-null**,
  so a `--fan-out` (or split/restructure) run syncs only the newly minted
  children and never re-creates the already-synced root's remote issue as a
  duplicate; a split run's already-synced root has its remote issue
  **updated** instead. Product-flow delivery tickets ("Product definition
  (PRD)", "Product architecture doc set") are excluded from this set and
  always stay unsynced. A sync failure for any one ticket in the set is
  surfaced (never silently swallowed) and does not abort the rest of the
  batch; that ticket's `external` stays `null` for a later retry. `external`
  is written into each synced ticket's own `ticket.json` by the
  deterministic write seam `record-external.py`.
- **Group-B issue-item field sync (standing behavior, MAR-103):** at
  creation, Priority, Story Points, and Parent sync to the board's matching
  named field (fixed case-insensitive table: `Priority`; `Story
  Points`/`Points`/`Estimate`; `Parent`/`Epic`) using type-driven value
  mapping, reusing the existing Project `field-list` call. A
  schema-undefined field is surfaced as an info finding (mirroring the
  GitHub-native reconciliation bullet above); a `null` ticket value for a
  defined field is skipped silently as expected data, mirroring the
  null-assignee rule.

## 2. `/create-design` *(conditional)*

Purpose: settle the system design before implementation is specified — for
tickets where the change is architecturally significant.

- Runs only when the ticket carries **`needs_design: true`** (set for epics
  only; stories/tasks are always `false` and skip straight to `/code`, unless
  they inherit a parent epic's design). All other tickets skip straight to
  `/code`.
- MUST analyze the ticket, the codebase, and existing docs; MUST evaluate
  **multiple options with trade-offs** and interact with the user on the
  genuinely open decision points before settling.
- MUST take the product architecture doc set (found in the repo) as
  primary input when it exists: the design either **conforms to the
  documented architecture** or explicitly lists the architecture changes it
  requires — which `/code` then applies to the doc set as part of the
  change.
- Produces **`design.md`** in the ticket's docs folder
  (`docs/tickets/<ID>/`) — the executor drafts it
  under `phases/create-design/` and the coordinator publishes the verified
  bytes — with required sections:
  **context & constraints (incl. NFRs such as security and performance),
  options considered, decision & rationale, architecture (components,
  interfaces/contracts, data model, and Mermaid sequence diagrams for new or
  changed flows), impact & risks, rollout/migration**.
- Child tickets of an epic do NOT repeat design: their `/code` reads
  the **parent epic's** `design.md` (cross-partition read,
  [workspace-and-state.md](workspace-and-state.md)).
- The `create-design-verifier` checks: alternatives genuinely weighed,
  consistency with the existing codebase and docs (including conformance
  with the repo's `standards/` doc set when it has one),
  feasibility, NFR coverage, and a deterministic `structure` floor
  (declared `required_sections`, **configurable** via
  `formats.design_template` / `enforcement.design_sections` — byte-identical
  to the built-in default when unset) — all findings block, including a
  blocking `audience-style` check (declared audience/style profile; an unwaived
  audience-mismatch blocks, a `clarify.py --source assumption` waiver makes it
  `severity="info"`, non-blocking) — same 3-iteration reflection cap.
- Subagents: `create-design-executor`, `create-design-verifier` (execute →
  verify, no planner — ADR-0092).
- The executor's survey also runs the shared ADR-0012 design-time
  doc-consistency step, surfacing gap/staleness findings through the
  existing clarification ledger.
- The design's accepted decision records are committed into the consumer
  repo's ADR folder (found in the repo, else `docs/adr/` —
  [configuration.md](configuration.md#document-and-workspace-locations)) by
  `/code` as part of its documentation updates.

> **Section numbering.** The numbers below are stable identifiers for these
> per-skill blocks, not the run order. The order the Build/Test/Ship steps
> run in is declared in `plugins/acs/workflows/ship.yaml`
> ([workflow.md](workflow.md#pipeline)); the lettered sections (2a–2d, 3a)
> are the Build/Test skills added by the skills-independence refactor, which
> land between the originally-numbered ones.

## 2a. `/analyze-requirements`

Purpose: the first Build step — understand the ticket against the product
docs and the codebase before anything is planned, and say plainly whether it
is ready to plan.

- Input: the ticket, the PRD / requirements / architecture doc sets, and the
  codebase. Pre-hook input check: the ticket resolves. Brake: an **epic** is
  refused (epics are designed and fanned out, never implemented).
- MUST write `analysis.md` to the ticket's docs folder with front matter
  `{ticket, ready_for_planning, api_surface, needs_design_recommendation}`
  and the sections: Problem restated; Impact
  map (components/files/tests likely touched); Questions; Assumptions;
  Risks; Refined acceptance criteria; Verdict.
- Every question MUST go through the clarification ledger — asked with
  AskUserQuestion when the user is reachable, else recorded
  `--source assumption` with a rationale. Refined acceptance criteria are
  **proposals** recorded in the ledger; the ticket's own criteria are
  amended only on user confirmation.
- MUST NOT set any rigor itself. The stakes recommendation this step used to
  run over the impact paths went with the axis (ADR-0095); what replaces it is
  EVIDENCE, not a setting. When the impact map reaches a surface the repo
  treats as load-bearing — auth, payments, a migration or any stored shape, a
  public API, concurrency or ordering — the analysis MUST say so in `## Risks`,
  naming the paths, because that is what `/create-impl-plan` carries into the
  plan and what the delivery-path judgement is then made from.
- A not-ready analysis MUST return `needs_input` rather than a completed run.
- `api_surface: true` is what makes `ship.yaml`'s `create-api-contract` step
  apply to this ticket; `api_surface: false` skips it.
- Subagents: `analyze-requirements-executor`, `-verifier` (execute → verify, no planner — ADR-0092).
- State file: `analyze-requirements-state.json`; states `ready_for_planning`,
  `api_surface`, `questions_open`.

## 2b. `/create-impl-plan`

Purpose: `/code`'s plan phase, carved out whole into its own skill, ending in
an approved `plan.md`.

- Input: the ticket, `analysis.md` and `design.md` when present (the API
  contract comes *after* the plan — the plan is what names the API surface
  to build). Pre-hook input check: the ticket resolves. Brake: an epic is
  refused.
- MUST keep every mechanism the phase had inside `/code`, unchanged: the
  survey (the former planner charter, carried by the executor since
  ADR-0092), the spec fold, the executor file map, plan approval
  (`standard`/`complex` only, run by those legs) and the plan-revocation path
  (`plan-superseded-<k>.md` in the workspace).
- MUST write `plan.md` to the ticket's docs folder (`docs/tickets/<ID>/`).
  It is always authored by the executor:
  the ADR-0074 fast path, on which the coordinator authored the plan itself
  with no executor spawn, went with the lanes it forked on (ADR-0095). The
  verifier judges every draft, and on blocking findings the executor authors
  the remediation (ceiling 3
  verify rounds — ADR-0074's 2026-09-14 amendment), so a fixable draft does
  not fail the run on its first verdict.
- MUST plan against the ticket as written when `analysis.md` says
  `ready_for_planning: true`: the ledger entries `/analyze-requirements` left open
  alongside that verdict (refined-criteria and missing-criterion proposals)
  are carried in the plan's Risks as `C-<n> open — planned as written`, never
  re-asked and never a `needs_input` — the analysis skill's own contract
  ("with no user answer … `/acs:create-impl-plan` plans against the ticket as
  written"). Only the plan's own genuine ambiguities and the oversize
  question are asked.
- Subagents: `create-impl-plan-executor`, `-verifier` (execute → verify, no
  planner — ADR-0092; the executor's survey inherited the `code-planner`
  charter).
- State file: `create-impl-plan-state.json`; states `plan_path`,
  `plan_approved`, `file_map`.

## 2c. `/create-api-contract`

Purpose: pin the API surface a ticket changes before it is implemented, so
`/code` builds against a contract and `/create-test-docs` derives cases from
it.

- Input: `plan.md`, `analysis.md`, the ticket, the architecture doc set, and
  the repo's existing contract files, wherever the repo keeps them (else
  `docs/api/`). Pre-hook input checks:
  `plan.md` exists **and** `analysis.md` declares `api_surface: true` —
  otherwise the skill is refused with a pointer at `/create-impl-plan` or
  `/analyze-requirements`.
- MUST write `api-contract.md`: every endpoint/command/message the plan adds
  or changes, request/response shapes, error codes, compatibility and
  versioning notes, and examples — each traced to an acceptance criterion
  **and** to a plan item.
- MUST update the repo's machine-readable contract files where the repo
  keeps them (else create them under `docs/api/`), committed on the ticket
  branch.
- Subagents: `create-api-contract-executor`, `-verifier` (execute → verify, no planner — ADR-0092).
- State file: `create-api-contract-state.json`; states `contract_path`,
  `items`, `traced_acs`.

## 2d. `/create-test-docs`

Purpose: turn the ticket's acceptance criteria (plus the plan and the API
contract when they exist) into an explicit, traceable set of test cases,
before any test is written.

- Input: the ticket's acceptance criteria; `plan.md` when present;
  `api-contract.md` when present. Pre-hook input check: the ticket resolves.
- MUST write `test-cases.md` with front matter `{ticket, cases}` and a
  table/list of cases: id `TC-n`, traced acceptance criterion, type
  `unit | integration | e2e`, preconditions, steps, expected result, target
  suite/module.
- **Every acceptance criterion MUST be traced by at least one case**; a
  completed run leaves `untraced_acs` empty.
- The e2e-typed rows are the input `/create-e2e-tests` reads, and the count
  of them is what decides whether that step has anything to do.
- Subagents: `create-test-docs-executor`, `-verifier` (execute → verify, no planner — ADR-0092).
- State file: `create-test-docs-state.json`; states `cases`, `e2e_cases`,
  `untraced_acs` (MUST be empty on a completed run).

## 3. `/code`

Purpose: implement the run's approved plan in the consumer repo using TDD.

> **`/code` neither plans nor reviews.** The plan phase left for
> `/create-impl-plan` (§2b) and the review left for `/review-code` (§3b).
> What remains is the implementation itself: read the plan, write the tests
> first, write the code, commit on the run's branch. `/code` REQUIRES an
> approved `plan.md` and produces none; it writes no verdict and grades
> nothing. Since ADR-0092 the plan charter is the survey of
> `create-impl-plan-executor.md`, and every `code-planner` mention below
> reads as that executor's survey. When execution finds the plan itself
> wrong, `/code` ends `failed` with `stop_reason: plan_superseded`, which
> `ship.yaml`'s loop routes back to `/create-impl-plan`.

**Plan authoring (folded into `/create-impl-plan` — ADR 0066).** The plan's
author — always `create-impl-plan-executor` — writes the implementation
content itself inside `plan.md`. The obligations below bind that step; they
are stated here because `/code`'s execute phase anchors on their outputs:

- MUST analyze and clarify the ticket (asking the user where ambiguous).
- MUST decompose the work into executor tasks with an honest file map, and
  MUST write the plan into the RUN directory —
  `<run>/steps/create-impl-plan/plan.md` — so `/code` can consume it without
  conversation history.
- Plan format: **markdown** with required sections — **scope, approach,
  API/data changes, test plan, out of scope** — plus the `## Contract` block
  (§2b) and `## Executor tasks & file map`. The **approach** section stays at
  contract level (components, interfaces, algorithms, error handling;
  indicative paths at most) — the authoritative file map is its own section.
  The **test plan** MUST state the **e2e impact** when `e2e` is configured or
  the change affects user-facing flows (the tests land in the same
  changeset), else "no e2e impact" with a reason.
- The **API/data changes** section SHOULD call out the documentation impact
  (which consumer-repo docs the change touches), so `/code` knows what to
  update.
- When a design exists (the ticket's own or its parent epic's), the plan MUST
  **conform to it**, and `/review-code`'s lens C MUST check that conformance
  against `design.md` and the architecture doc set.
- **Plan-simplicity gate (MAR-88):** the plan's author MUST evaluate each
  candidate decomposition for a **materially** simpler alternative that meets
  the **same acceptance criteria** with materially less code/complexity,
  before the plan is published. A found alternative is **surfaced** (never
  blocked or auto-looped back) to the user/plan owner for a **decision**,
  through the coordinator's existing User-interaction path — the threshold is
  "materially" simpler, never a naming or style preference. Deconflicted from
  the review's craft lens (plan-time vs code-time simplicity; see
  [reflection.md](reflection.md)) — author-charter-only, no new review check
  is added.
- MUST escalate an **oversized ticket** instead of producing a monster plan:
  when an honest decomposition exceeds ~4 executor tasks (or the surface
  clearly exceeds a reviewable diff), stop, record the split seams, and route
  to `/create-ticket split <id>` (user-confirmed); the user MAY explicitly accept
  one large PR, recorded as a clarification. Implemented as a two-lever
  control after ADR 0066 (ADR 0069): `/create-ticket`'s upfront PR-size rubric
  fires before any decomposition exists; a non-blocking, plan-time oversize
  signal in the survey's charter item 2 fires once the decomposition itself is
  known, reusing the plan-simplicity gate's "surface, never block" contract to
  raise the same question through the clarification ledger. On a "split"
  answer the step ends `"failed"` with a `summary` naming the split, runs
  its mandatory Finish steps, and points at `/acs:create-ticket split <id> per
  steps/create-impl-plan/plan.md`.
- **Plan-artifact naming (MAR-70; MAR-70 resume fallback retired by
  MAR-73).** The plan artifact is a single per-run
  `<run>/steps/create-impl-plan/plan.md`, authored by
  `create-impl-plan-executor`, written exactly once per run, before `/code`
  starts. `plan.md` is the only name ever read or written for it, in every
  case. The approval mirror under `steps/code/` is retired: one file, one
  path, read by every step that needs it.
  `<run>/steps/create-impl-plan/plan-superseded-<k>.md` is the plan-revocation
  path's superseded-plan artifact — a byte-identical copy of the revoked
  `plan.md` (copy, never a move/rename), written at an iteration/run boundary
  so existing citations resolve unchanged; it is never an approval input and
  never a conformance contract (MAR-74, slice 4 of MAR-69).
- **Loop topology.** `/code` has no loop of its own. The plan is authored
  exactly once per run, and the remediation loop is the WORKFLOW's:
  `ship.yaml`'s `loops[]` sends the cursor from `review-code` back to `code`
  when the verdict records blocking findings, up to
  `loops[].max_iterations` — one cap, the same on every delivery path. On
  iteration 2+ the confirmed findings are delivered to the executor's
  `<context>`; no planner runs between the review and the fix (ADR-0092).
- **Plan approval (MAR-73, slice 3 of MAR-69).** On the **`standard`** and
  **`complex`** delivery paths only, at the leg's Start, `/code` MUST record a
  **deterministic plan-approval verdict**: `plan-approval.py` computes
  `acs_lib.plan_approval_eligible` from the plan artifact's own content plus
  `settings.test_coverage_percent` and is the **sole writer** of
  `<run>/steps/code/plan-approval.json` — never a subagent's `Write`, never
  the coordinator's, never an LLM self-assertion. The record carries the
  predicate's inputs, checks, failures and the approved plan's **sha256**, and
  is written **at most once per approved plan digest** (idempotent on resume;
  a revised `plan.md` writes a fresh record). `states.plan_approved` is
  `false` on the `trivial` and `small` paths (no record is written at all) and
  on an ineligible plan. An ineligible plan **does not block**: the run
  continues, at most revising `plan.md` once and re-running the script.
  **Nothing gates on `plan_approved`** — `/create-pr`'s brake is the review's
  derived `verifier_passed` alone.
- **Plan revocation (MAR-74, slice 4 of MAR-69).** When a blocking
  `kind: contract` finding's remedy is that the *plan* is wrong, the run MAY
  revoke the plan — **never automatically**, only at an iteration/run boundary
  and only on an explicit `clarify.py`-recorded user answer; the sequence is
  copy (`plan-superseded-<k>.md`, `<k>` the smallest free positive integer) →
  re-run `/create-impl-plan` → re-run `plan-approval.py` for a fresh record.
  Superseded copies are the audit trail and are never deleted, never an
  approval input, never a conformance contract.

`/code`'s own obligations follow:

- MUST analyze and clarify the plan before coding. This is plan-level
  clarification of the content it implements, as distinct from the
  ticket-level clarification the plan itself required.
- MUST implement features, bug fixes, and tasks using the **TDD pattern**:
  write tests first, then implementation, iterating until green.
- MUST generate unit tests and run them targeting the configured
  `test_coverage_percent` (default 90) from `settings.json` — measured once,
  at the review's gate, never inside an iteration that may be discarded.
- MUST run the tests its change touches, not the full suite: the full suite is
  the review's final gate, run once, last, on the iteration that survives
  review. That discipline is safe precisely because the gate is unconditional
  and terminal rather than buried inside an iteration that may be discarded.
- MUST update the consumer repo's **documentation affected by the change**
  as part of the implementation: README, API/usage docs, code comments, the
  changelog where the repo keeps one — and the **product architecture doc
  set** (found in the repo) whenever the change adds or removes
  components, or alters the data model, integrations, or deployment: HLD
  (C4 views, data model, deployment) updated accordingly, and the ticket
  design's new/changed **sequence diagrams merged into `lld/flows/`** —
  following the repo's existing conventions. MUST also merge the ticket's
  acceptance criteria and behavior-defining clarifications into the touched
  feature area's file in the requirements set (the living requirements —
  [workflow.md](workflow.md#living-requirements)). Docs work is part
  of the change, not a follow-up.
- **ADR-0012 participation (bounded, touched-area, post-plan — third
  amendment).** The plan survey's item 4 detects, for the touched area
  only, four bounded missing doc-graph edges (E1-E4; full table at
  `create-impl-plan-executor.md`'s item 4): a touched/added component missing
  from the C4 component doc, a touched/added persisted entity or state
  shape missing from the data model, a touched/added runtime flow
  missing an `lld/flows/` sequence diagram, and a user-visible
  capability missing a PRD goal or roadmap row — carried on the SAME
  `problems` field the Boy-scout drift item already uses into
  `/acs:docs-sync`. This is **not** the full ADR-0012 design-time
  step: living-requirements edges and ADR edges are explicitly
  not covered by it and remain the responsibility of
  `/acs:create-design`'s full step (for `needs_design: true` tickets)
  and `/acs:docs-sync`'s diff-grounded re-derivation.
- Commit messages MUST follow the commit message format configured in
  `settings.json` ([configuration.md](configuration.md)).
- `/acs:code` MUST NOT review its own changeset. The review is
  **`/acs:review-code`** (§3b), a step of its own, and every delivery path
  gets the same one. An implementer that grades its own output gave
  per-finding adjudication to one path out of four and ran the full unit suite
  inside an iteration that might be discarded.
- MUST record progress, findings, errors, and stop reasons so an interrupted
  run can resume; final state lands in `steps/code/state.json` via the
  post-hook.
- On start, if the previous invocation is `interrupted` or `failed`, `/code`
  MUST **reconcile** before continuing: verify recorded progress against
  reality (e.g. re-run tests for tasks marked implemented) and resume from the
  first unfinished task ([workflow.md](workflow.md#resuming-a-ticket)).
- The pre-hook MUST verify that the run resolves, that an approved `plan.md`
  exists for it (the input `/code` consumes rather than produces — a run
  without one is refused with a pointer at `/acs:create-impl-plan <id>`), and
  that the subject ticket's own `type` is not `epic`: an epic is refused
  outright with a `GateError` directing the user to `/acs:create-design` (if
  the epic has no design yet), then `/acs:create-ticket <id> --fan-out`, then
  `/acs:code` on a child. The epic brake is unconditional and runs for every
  implementation step, not only this one.
- Subagents: `code-executor` and nothing else. `/code` ships **no planner**
  (the plan phase moved to `/create-impl-plan`, §2b) and **no verifier** (the
  review moved to `/review-code`, §3b). The four delivery-path legs
  `code-trivial`, `code-small`, `code-standard` and `code-complex` own no
  agents of their own: each spawns this same executor, and what varies is how
  many and over which partition of the plan's file map.
- When the coverage target cannot be reached, the run MUST **hard fail** at
  the review's gate: coverage is a `kind: gate` blocking finding with the
  failing command as its evidence. A failed review leaves `verifier_passed`
  false, which is what `/create-pr`'s brake refuses.
- On a **`docs_only`** ticket the TDD steps relax (no new tests, no coverage
  measurement) but the guarantees do not: the full suite still runs once at
  the gate and must stay green, and executable-code diffs under the flag are
  blocking findings.
- When **`e2e`** is configured ([configuration.md](configuration.md)):
  executors author the e2e tests their tasks declared (same changeset) and run
  the affected subset; the full e2e suite is `/acs:run-e2e-tests`' own step
  (setup → command → teardown, always).
- `/code` works on a dedicated git branch (and optionally a worktree) per run;
  the branch name follows `formats.branch_name` from `settings.json` and
  embeds the `<ticket-id>` so later skills and hooks can resolve context from
  it.

### The delivery path is judged once (ADR-0095)

`/code` used to escalate mid-flight: when an in-flight signal revealed the work
was larger or higher-stakes than its original classification, the coordinator
recomputed the lane, raised the verify ceiling, re-persisted the axes to three
state files, and appended a thirteen-field audit event — all without restarting
the run (MAR-57). Three triggers could fire it, one of them deterministic
(a `high_stakes_paths` glob match), and the whole contract was upward-only so
that nothing could quietly lower rigor a user had confirmed.

None of that survives. A run is judged onto ONE delivery path — `trivial`,
`small`, `standard` or `complex` — by `/create-impl-plan`, and that judgement
stands for the run:

1. **One judgement, from the plan.** `/create-impl-plan` judges the path from
   the work itself and records it in the plan's `## Contract` block, using the
   rubric in `skills/code/references/classify.md`. The plan is the first
   artifact that says what the change actually IS — its file map, its test
   strategy, the surfaces it names — rather than what the request sounded like
   before anyone read the code, which is what the axes were guessing at.

2. **Recorded once, read thereafter.** The path and the one-sentence reason
   for it live in the plan's `## Contract` block, as `delivery_path` and the
   `owes.reason` beside it — one artifact, written once and never re-judged.
   `/code` dispatches to the leg the plan names; a resumed run reads the same
   recorded value instead of judging again and splitting one run across two
   rigors. Nobody picks a path by hand, and a path passed as an argument is
   refused.

3. **No raise, no lower, no ceiling arithmetic.** There is no `derive_lane`,
   no `verify_depth`, no iteration-ceiling recompute and no escalation event,
   because there is nothing to move. The one ceiling is `ship.yaml`'s
   `loops[].max_iterations`, which the workflow owns and no leg restates.

4. **What catches a wrong judgement is the review, not a trigger.** A leg that
   believes the path is wrong for the work in front of it says so with
   `stop_reason: needs_input` rather than behaving like another leg, and
   `/review-code` judges the diff against the plan it was written from. The
   remedy is a replan — the run fails with `stop_reason: plan_superseded` and
   the loop returns to `/create-impl-plan` — never a mid-run re-route, because
   half a run at one rigor and half at another is exactly what this replaces.

5. **What got worse, and why that is accepted.** Rigor can no longer RISE
   mid-run, so a plan that understates the work is caught at the next review
   rather than the next iteration. The cost is bounded by the replan; the thing
   bought is that every run has one rigor, decided from evidence, with a
   recorded reason a reviewer can read.

6. **Sibling behavior unchanged.** The apply-tier inlining (MAR-60:
   `create-pr` → `merge-pr` → `create-ticket`) is unaffected.

## 3b. `/acs:review-code`

Purpose: judge the changeset `/acs:code` produced, and be the only place the
full unit suite runs.

- `/acs:review-code` is a **step of the workflow**, not a phase inside
  `/acs:code`, and it runs on **every** delivery path. It reviews the
  changeset — not one executor's output, not one iteration's diff — against
  the gated upstream contracts.
- It MUST review in three stages:
    1. **Five read-only lenses in parallel**, each bounded by what it may
       read: **A** acceptance (requirements, the plan, `test-cases.md`, the
       diff), **B** changed-hunk defects and security (**the diff and nothing
       else**), **C** contracts and architecture (`api-contract.md`,
       `design.md`, architecture docs, the plan), **D** history and regression
       (`git log --follow -p`, bounded lookback), **E** craft and scope
       (the repo's `standards/` set, the diff; **Simplicity & scope** —
       overcomplication and out-of-scope edits — is blocking and lives here).
       Lens B fans out across the diff when the diff warrants it, measured
       from the changeset rather than passed in; lens D runs on **every** run.
    2. **One fresh-context adjudicator per candidate finding**, prompted to
       refute it, receiving neither the other findings nor which lens raised
       it, defaulting to refuted when uncertain. `confirmed` blocks and
       carries a `resolved_when`; `refuted` is dropped with its reason
       recorded; `needs-context` downgrades to advisory and is carried.
       Corroboration is NOT a filter — per-finding re-derivation is.
    3. **A final gate**, only when stage 2 leaves nothing blocking: build,
       lint, the full unit suite, and coverage against
       `settings.test_coverage_percent`. This is the only place the full suite
       runs in the pipeline. A gate failure is a blocking finding of
       `kind: gate` with the failing command as its evidence.
- `/acs:review-code` MUST review the changeset — **business logic**,
  **features** (does it satisfy the ticket and the plan), **quality**,
  **technical standards** (conformant with the repo's `standards/` doc set
  when it has one; falls back to documented architecture when it has
  none), **architecture**, **system design**, **security**,
  **documentation** (affected docs updated and consistent with the code),
  **Simplicity & scope** (overcomplication and out-of-scope edits are
  blocking), and **plan conformance** (blocking when active, N/A otherwise;
  active only when a deterministic approval record exists whose plan path is
  the run's `plan.md` and whose digest matches its current bytes; the
  reviewer computes activation itself; strictly **subordinate to acceptance
  conformance**, which an approved plan can never substitute for).
- The step's conclusion is a **document**, not a status: `verdict.json` under
  `<run>/steps/review-code/`. Completing the step without a usable verdict is
  refused. `verifier_passed` is **derived** by the post-hook from that verdict
  and never asserted by a coordinator
  ([workflow.md](workflow.md#review-feedback-loop)).
- Blocking findings re-enter the loop: `ship.yaml`'s `loops[]` returns the
  cursor to `code`, up to `loops[].max_iterations`, and `on_exhausted: fail`
  means a run that cannot clear its findings fails rather than passing with
  them.
- Subagents: `review-code-lens` and `review-code-adjudicator`. That is not an
  executor/verifier pair and is not meant to be — the two roles fan out
  independently of each other.

## 3a. `/create-e2e-tests`

Purpose: write the ticket's end-to-end suites from the e2e-typed rows of its
test cases, so the post-code e2e run has something ticket-specific to run.

- Input: the e2e-typed rows of `test-cases.md` and the repo's e2e
  configuration (`settings.e2e` / `settings.suites.e2e`). Pre-hook input
  checks: an e2e suite is configured **and** `test-cases.md` lists at least
  one e2e case — a repo with no e2e layer is refused with a pointer at adding
  `suites.e2e` to `.acs/settings.json`, and `ship.yaml` skips the step for it entirely
  (`when: e2e_configured`).
- MUST write the suites at the repo's configured e2e location, named after
  the ticket, committed on the ticket branch.
- Runs **in parallel with `/docs-sync`** in the default workflow — both need
  only `code` — as two legs in two worktrees
  ([workflow.md](workflow.md#parallel-work)).
- Subagents: `create-e2e-tests-executor`, `-verifier` (execute → verify, no planner — ADR-0092).
- State file: `create-e2e-tests-state.json`; states `suites_written`,
  `cases_covered`.

## 4. `/docs-sync`

Purpose: re-verify and complete the doc updates a ticket's changeset
requires — independently re-derived from `git diff <default_branch>...HEAD`, `/code`'s
`result.json`, and the final code-verify artifact, never from a hand-off
summary alone.

- MUST confirm the current git branch matches the ticket's recorded branch
  before doing any work; docs-sync NEVER creates a branch and NEVER opens a
  PR — it always operates on the SAME ticket branch `/code` uses, adding
  commits to the existing changeset (same PR/review).
- MUST gather, and never substitute a bare hand-off summary for: the live
  `git diff <default_branch>...HEAD`, the ticket JSON, `/code`'s
  `result.json` (`states.docs_updated`), `/code`'s execute report(s)
  `problems` field, and the final code-verify artifact.
- Subagents: `docs-sync-executor`, `docs-sync-verifier` (execute → verify, no planner — ADR-0092).
- State file: `docs-sync-state.json`, written by the post-hook
  ([workspace-and-state.md](workspace-and-state.md)).
- Declared position: in the default `ship.yaml`, `docs-sync` needs only
  `code` and runs in parallel with `create-e2e-tests`; `create-pr` needs
  `docs-sync` and `run-e2e-tests`. That position is **declared, not gated** —
  `/docs-sync`'s own pre-hook checks the partition and the lock and nothing
  else, so a hand-run `/docs-sync` proceeds (after one advisory line) even
  when `/code` has not completed ([hooks.md](hooks.md)).

## 5. `/create-pr`

Purpose: ship the implementation as a pull request.

- MUST create a PR containing the new changes for the implementation. The
  ticket's branch already exists — created by `/code` per
  `formats.branch_name` — so `/create-pr` pushes it and opens the PR.
- SHOULD compose the PR title/description from workspace state (ticket,
  specs, `code-state.json` summary incl. review findings) rather than
  conversation history.
- MUST record the PR reference (number/URL) in the workspace state.
- Inline shape (MAR-55 invariant (b)): the coordinator runs apply-work
  directly, optionally delegating to at most one `create-pr-executor`
  subagent; no planner subagent; no verifier subagent. Correctness was gated
  by the upstream review (`/acs:review-code`); the human checkpoint is the PR review.
- PR title and PR description MUST follow the formats configured in
  `settings.json` ([configuration.md](configuration.md)).
- The PR targets the repo's **default branch** and MUST carry the **`ACS`**
  label.
- **[ASSUMPTION]** PRs are created ready-for-review (not draft).
- **GitHub-native issue linking (standing behavior, MAR-75):** for a ticket
  synced to GitHub the PR body carries a `Closes #<external.key>` reference (a
  distinct bullet in the `## Ticket` section) so GitHub auto-links and
  auto-closes the issue on merge, in addition to the existing `[{ticket_id}]`
  title and tracker line. The PR also carries the required `ACS` label and the
  milestone when one is used. The link bullet is omitted entirely for
  `local`/unsynced tickets. Independently, the enforced `pr_title` format now
  renders the tracker's native reference when the ticket is synced (MAR-80) —
  see the `/create-pr` section above for the title-rendering mechanics.
- **Tracker-metadata fill (standing behavior, MAR-101):** on GitHub tracker
  sync (i.e. `ticket.external.provider == "github"` and the ticket is synced),
  an acs-opened/updated PR carries assignee = PR author (the authenticated
  `gh` user, resolved via `@me`) on both the create and edit paths; the
  ticket-type label alongside the required `ACS` label, both created
  idempotently; and Project membership with its Status field set — any
  Project-schema-undefined field is surfaced as an info finding rather than
  silently skipped (mirroring the create-ticket standing behavior above).
  `local`/unsynced tickets are unaffected (byte-identical no-op), and a
  failed `gh` metadata call is surfaced as a finding and never aborts the PR.
- **In Review Status transition (standing behavior, MAR-102):** the
  tracker-metadata fill's Status-set call resolves the in-review option by
  case-insensitive name (`In Review`, then `Review`) on both the create and
  edit paths. When the board defines no such option, an info finding names
  it and how to add it; Status is left unchanged and the PR is unaffected.
- **CODEOWNERS-derived reviewers (standing behavior, MAR-103):** on GitHub
  tracker sync, an acs-opened/updated PR requests reviewers derived from a
  CODEOWNERS-derived resolution over the PR's changed files (last-match-wins,
  team-slug-aware); the PR author is always dropped from the candidate set.
  An empty or author-only result skips the reviewer request gracefully with
  an info finding naming the exact reason — never a hard failure, and
  `--add-reviewer` is never called on an empty set.
- **Group-B PR-item field sync (standing behavior, MAR-103):** Priority,
  Story Points, and Parent sync to the board's matching named field (fixed
  case-insensitive table: `Priority`; `Story Points`/`Points`/`Estimate`;
  `Parent`/`Epic`) using type-driven value mapping, reusing the existing
  Project `field-list` call. A schema-undefined field is surfaced as an
  info finding, mirroring the existing fallback above.
- **Stacked-base pre-flight (standing behavior, MAR-590):** step 1 detects the
  base branch and then runs a read-only, network-free pre-flight over the
  branch's commit range BEFORE anything is pushed; the caller performs the
  `git fetch` the helper deliberately does not. Base detection moves into step 1
  and is **critical**, so its failure stops the run before the push rather than
  after it. On a stacked-base verdict the run MUST stop before the push: no
  push, no `gh pr create`/`gh pr edit`, the report's `message` surfaced
  VERBATIM as a blocking problem, and no PR created — so a `/create-pr` run can
  now end with no PR. A pre-flight that cannot evaluate the condition is
  advisory — one `info` finding and the run continues — and a failed
  `git fetch` is treated the same way. A not-stacked verdict whose report
  carries a non-empty `notes` is advisory too, never conclusive: the report's
  `message` accounts for every `notes` entry, each named exactly once, on both
  the stacked and the not-stacked message shape, and the run MUST NOT read such
  a report as evidence that the non-conforming subjects are the branch's own —
  it surfaces that `message` as an `info` finding and continues. Detection is
  deliberately incomplete and never authoritative: it reports before the push
  rather than preventing the conventions-gate failure, a miss degrades to the
  ordinary red gate with no replay advice rather than to a false alarm, one
  false positive is accepted deliberately, and a degraded run can add a second
  that the report announces. The skill never runs the rebase or the force-push;
  the author does. Stacking remains permitted and the repository's merge
  strategy is unchanged.

## 6. `/merge-pr`

Purpose: land the change.

- `/merge-pr` is **agent/model-invocable** (MAR-42): it MAY be invoked by the
  user or an authorized agent. The readiness gate (CI, approvals, conflicts,
  branch protection) is the brake — a merge proceeds only when it passes plus
  the repo's branch protection, by whoever invokes; an **approving review is
  required** (mitigation m6). `/acs:ship` still stops at `/create-pr` and never
  invokes `/merge-pr` itself. A failed readiness check is report-only.
- MUST review PR readiness — **[ASSUMPTION]** at minimum: CI status, review
  approvals, merge conflicts, branch protection requirements.
- Product-level delivery tickets (PRD, architecture, scaffold) merge like
  any other ticket — the PR reference is read from the skill's state file in
  the ticket partition
  ([Product-level delivery](#product-level-delivery-tickets)).
- MUST merge the PR **if possible**; if not possible, it MUST record the stop
  reason in the workspace state and report what is blocking. A failed
  readiness check is **report-only**: `/merge-pr` never routes fixes back to
  `/code` automatically.
- When the merged ticket is the last open child of an epic, the epic MUST be
  auto-marked done ([workflow.md](workflow.md#epic-fan-out)) —
  performed by the `post-merge-pr` hook.
- Inline shape (MAR-55 invariant (b)): the coordinator runs apply-work
  directly, optionally delegating to at most one `merge-pr-executor`
  subagent; no planner subagent; no verifier subagent. Correctness was gated
  by the upstream review (`/acs:review-code`).
- Merge strategy is configurable via `merge_strategy` in `settings.json`
  (`squash` | `merge` | `rebase`), default **`squash`**.
- Post-merge actions (all required): **delete the branch**, **clean up the
  worktree** (if one was used), and **mark the ticket done** — in workspace
  state, in the remote tracker (if synced), and by archiving the ticket
  partition ([workspace-and-state.md](workspace-and-state.md)).
- **BEHIND auto-update (standing behavior, MAR-47):** When
  `mergeStateStatus == BEHIND` and every other readiness dimension (ci,
  approvals, conflicts, protections-other-than-BEHIND) passes, the standing
  behavior is to run `gh pr update-branch <number>` (merge-update — no
  `--rebase`, no force-push), poll required CI checks at 15-second intervals
  for up to 5 minutes (C-6), and then merge in the same invocation. Up to 2
  total update-branch attempts are made if the base advances again mid-poll
  (C-8); after the cap → report-only. An update-branch conflict or a CI poll
  timeout falls back to report-only — bounded exceptions, not the standing
  behavior. This carve-out applies to **both** the ticket path and the exempt
  `--pr` path (C-10). All other clauses above (agent-invocable, m6
  require-APPROVED, report-only for other failures, post-merge cleanup, merge
  strategy) remain intact and unchanged.
- **Reconciliation close-comment (standing behavior, MAR-75):** when the
  merged ticket is synced to GitHub, the `gh issue close` comment records the
  acs ticket id and a back-reference to the merged PR (`Merged {ticket_id} via
  PR #{pr.number} — {pr.url}`), so the closed issue's timeline still reaches
  both the acs ticket id and the PR. The `gh issue close` call and the
  Status→Done edit are otherwise unchanged.
- **GitHub call failure policy (standing behavior, MAR-403, ADR-0088):** `gh`
  is this skill's only GitHub transport. A readiness *dimension that
  evaluates to fail* stays report-only, unchanged. A readiness *read that
  cannot be evaluated* because the `gh` call itself failed is **critical**:
  verbatim `gh` stderr plus one canonical `acs_lib.gh_failure_hint()` hint,
  and the run **stops before any merge is attempted** — an unevaluable gate
  is never treated as passed. This applies identically to the Step 0
  readiness reads, the resume/reconcile `gh pr view`, the BEHIND carve-out's
  `gh pr update-branch` call and its required-checks poll, and the exempt
  `--pr` path's identical reads. Separately, once the merge has landed, the
  post-merge tracker sync (`gh issue close`, Status→Done) is
  **loud-but-non-reverting**: a failure there produces one error-severity
  finding naming the outstanding sync plus a replayable command block; the
  merge is never reverted or re-attempted; and the run still finishes
  `merged: true` — this qualifies, without changing, the post-merge actions
  and reconciliation close-comment bullets above.
