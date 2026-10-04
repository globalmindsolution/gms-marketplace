# Skill Requirements

Twenty-eight skills in total. There is no registry file listing them: a skill is
a **directory** under `plugins/acs/skills/` holding a `SKILL.md`, and that is the
whole of what makes it a skill (§2.4). Nothing declares what a skill reads or
writes, or which group it belongs to, because nothing needs to: each skill
reads what it finds and falls back to the run's subject when an upstream
artifact is absent.

The groups below are a reader's aid, not a structure the code knows about:

- **Product & design** — `/acs:create-prd`, `/acs:create-architecture`,
  `/acs:create-ticket`, `/acs:create-design`, `/acs:create-data-design`,
  `/acs:create-flows` (the last two write a ticket's low-level design,
  [ADR-0126](../../architecture/adr/0126-lld-data-design-and-flows.md)). The quality, operations,
  principles and standards doc sets are written by hand: no skill bootstraps
  them since `/acs:create-docs` was removed
  ([ADR-0124](../../architecture/adr/0124-remove-create-docs.md)), and the
  skills that read them find them where the repo keeps them.
- **Implementation** — `/acs:analyze-requirements`,
  `/acs:create-impl-plan`, `/acs:create-api-contract`,
  `/acs:create-test-docs`, `/acs:code` and its four delivery-path legs,
  `/acs:review-code`, `/acs:docs-sync`.
- **Test** — `/acs:create-e2e-tests`, `/acs:run-e2e-tests`.
- **Ship** — `/acs:create-pr`, `/acs:merge-pr`, `/acs:release`.
- **Audit** — `/acs:audit-design` (the design compared with the code),
  `/acs:audit-security` (the repository's security): read-only, ticketless,
  runnable at any time, each writing a report
  ([ADR-0123](../../architecture/adr/0123-audit-phase-and-audit-security.md)).
- **Utility** — `/acs:setup`, `/acs:update`, `/acs:handoff`, `/acs:ship`.

The ORDER of the implementation skills is `workflows/ship.yaml`'s list, and
nothing else states it. A run's progress over that list is `run.json`; a
skill's own progress inside a step is `steps/<skill>/state.json`.

The phase a skill sits in is a grouping, not an order. The order the Build,
Test and Ship steps run in for a ticket is declared in
`plugins/acs/workflows/ship.yaml` ([workflow.md](workflow.md#pipeline)), and
**every skill MUST be runnable on its own** — a skill MUST NOT refuse to run
because another skill has not run ([hooks.md](hooks.md)).

Nineteen of the twenty-eight are **hooked** (a pre-hook and a post-hook
each): the six Product & design skills, all seven Implementation skills,
both Test skills, `/create-pr`, `/merge-pr` and both Audit skills. Five (`/setup`, `/ship`,
`/handoff`, `/update`, `/acs:release`) are unhooked and take no position in a
run. The remaining four are `/acs:code`'s delivery-path legs, gated as `code`
itself. `/run-e2e-tests` is a hooked step like any other; the `/acs:test`
alias is removed. A greenfield repo's scaffold is no skill of its own
([ADR-0118](../../architecture/adr/0118-discovery-design-development-phases.md)): it is a
ticket — `/acs:create-ticket "Scaffold the repository per the architecture
docs"`, then `/acs:ship`.

Every **workflow** skill MUST:

- spawn only the subagents its own work needs, each named for what it does
  (ADR-0109; [reflection.md](reflection.md)): a `survey` role that reads
  and records notes and questions, a `write` role that produces the
  deliverable, a `judge` role that re-derives and judges it fresh. The
  eleven **authoring skills** run a write → judge Reflection cycle over
  their own roles — `analyze-requirements` (analyst, impact-analyst, impact-reviewer),
  `create-prd` (surveyor, author, reviewer),
  `create-architecture` (architect, gap-analyst, reviewer), `create-design` (designer,
  design-reviewer), `create-data-design` (designer, gap-analyst, reviewer),
  `create-flows` (designer, gap-analyst, reviewer), `create-impl-plan`
  (planner, plan-reviewer), `create-api-contract` (contract-author,
  contract-reviewer), `create-test-docs` (test-designer, trace-reviewer),
  `create-e2e-tests` (test-writer, suite-runner) and `docs-sync` (doc-updater,
  drift-reviewer). No skill has
  a plan phase before its writer (ADR-0092). `code` spawns implementers only —
  its review is `/review-code`, which runs lenses and adjudicators. Three
  **apply-work skills** (create-pr, merge-pr, create-ticket) run **inline**
  per MAR-55 invariant (b): the coordinator performs the apply-work directly
  from its `references/` and spawns no subagent, on every delivery path.
  `/acs:audit-design` is read-only and runs no write → judge cycle: it spawns
  gap analysts (a survey role) and reports what they found
  ([ADR-0122](../../architecture/adr/0122-design-versions-and-gap-detection.md)).
  `/acs:audit-security` is read-only too and has no writer: its auditors (a
  survey role) raise candidate findings and one adjudicator (a judge role) per
  candidate tries to refute it
  ([ADR-0123](../../architecture/adr/0123-audit-phase-and-audit-security.md)).
- have its safety brakes checked by a pre-hook and its outcome persisted by a
  post-hook ([hooks.md](hooks.md)) — neither hook enforces pipeline order,
  and neither refuses because an upstream artifact is missing;
- write state **only** inside `<workspace>/<repo>/<ticket-id>/`, and write
  the ticket's human-facing documents only under the fixed
  `docs/tickets/<ticket-id>/` (the consumer repo is
  otherwise touched only where the skill's job requires it, e.g. `/code`
  edits source files);
- read configuration from the `.acs` `settings.json`
  ([configuration.md](configuration.md)), and spawn each subagent on the
  model and effort of its role's tier configured there — `planner` for survey
  roles and `create-impl-plan`'s planner, `executor` for write roles,
  `verifier` for judge roles
  ([configuration.md](configuration.md#subagent-models)) (apply-work skills
  run inline and spawn none);
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

## `/setup` (optional)

Purpose: let a team change the branch/commit/PR conventions and install the
CI that enforces them — nothing else. It is **optional**: every setting has a
working default, so no skill needs `/setup` to have run first
([ADR-0105](../../architecture/adr/0105-acs-runs-without-setup.md)). Every other setting
(ticket prefix, coverage target, merge strategy, tracker, models, named test
suites, advisories) keeps its default and is edited by hand in `.acs/settings.json`,
validated against `settings.schema.json`.

- MUST write only the project settings file (`<repo>/.acs/settings.json`,
  committed — conventions are the team's); there is no scope question. MUST
  NOT write a value equal to its built-in default, and MUST remove one an
  earlier run wrote, so the file carries only choices.
- The workspace derives silently to `<main-checkout>/.acs/state-machine` —
  no prompt, no required input, and no override (ADR-0086,
  [ADR-0102](../../architecture/adr/0102-documents-are-found-not-configured.md)).
- MUST NOT ask for a `ticket_prefix`: it defaults to `ACS`, and a repo that
  wants its own sets it by hand.
- MUST show the three conventions — `formats.branch_name`,
  `formats.commit_message`, `formats.pr_title` — with their built-in
  defaults, and ask whether to keep or customize them.
- MUST ask which design documents the Design skills write: one multi-select
  per kind (`design.hld_types`, `design.lld_types`) from the catalog `setup
  detect` reports, defaults preselected, writing only a non-default choice
  ([ADR-0120](../../architecture/adr/0120-design-document-catalog-and-ticket-features.md)).
- MUST offer each CI gate explicitly, never installing one silently: the
  convention check (the PR description names its ticket,
  [ADR-0106](../../architecture/adr/0106-ci-checks-the-ticket-link-only.md)), the tests +
  coverage gate (which needs `tests.unit.command`),
  and the e2e merge gate — the last offered only when `tests.e2e` is
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
  also hide `.acs/settings.json`/`.acs/ci/*` from CI (ADR-0086). Nothing
  depends on these entries any more: the state root ignores itself through
  its own `.gitignore` of `*`, written on the first state write (ADR-0105).
- MUST name every retired settings key (ADR-0102) still in a settings file
  and say it is ignored.
- `/setup` is not part of the gated pipeline (no subagents); it is a
  simple setup skill.
- No other skill waits on `/setup`: a repo with no `settings.json` runs every
  skill on the defaults. A pre-hook still refuses (exit 2) a malformed
  hand-set value, such as a lowercase `ticket_prefix`.
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
- It invokes the ONE step `run next` names — or, when the cursor sits in a
  parallel group the list declares, every member `run next` reports in
  `due`, driven in lockstep inside its own session (ADR-0110). It MUST NOT
  decide on its own that two steps may overlap: `ship.yaml` v3 rejects
  `max_parallel` and `exclusive`, and what the old parallel mode bought — not
  paying for a step with nothing to do — is bought instead by the evidenced
  no-op, which costs no tokens and no worktree.
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
- No subagents of its own; each step skill is **invoked
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
- Not part of the gated pipeline; no subagents.
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
  [ADR 0103](../../architecture/adr/0103-no-status-line-no-cost-metering.md); the fix is
  removing that setting), workspace reachable.
- Reloading is the user's action (`/reload-plugins` or a new session); the
  skill states this explicitly — the current session keeps the old version.
- Not part of the gated pipeline; no subagents.

## /acs:run-e2e-tests (test)

Purpose: the standing, schedulable **suite runner** over the named suites of the
`tests` settings key — runs the product's configured test commands (unit,
integration, e2e, regression, or any other named suite) and reports results,
closing the loop on failures with a regression ticket.

- **Model-invocable** (it does not set `disable-model-invocation`): a
  natural-language request to run the configured test suites, run a named
  suite, or check whether anything broke routes here.
- **Argument contract:** no `--suite` flag runs every named suite in `tests`; one
  or more `--suite <name>` flags run only the named subset.
- **Unhooked** — like `/setup`/`/update`,
  `/acs:run-e2e-tests` spawns no subagents, has no pre- or
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
  See `docs/architecture/adr/0044-acs-test-closed-loop-ticketing.md` for the full policy.
- **Scheduling is the caller's job** — Claude Code routines/cron invoke
  `/acs:run-e2e-tests` headless; the concrete recipe lives in the skill's
  `references/test-scheduling.md`, not duplicated here.
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
  `docs/architecture/adr/0068-acs-test-ticket-scoped-fix-and-retest-mode.md`.

## /acs:release (utility)

Purpose: the one-command **release-cut** utility — assembles/verifies the
CHANGELOG section for a release version from the merged-ticket archive, and,
for tickets merged without an archive entry, from `base_branch` commit
history, bumps the version-location files plus any extra refs configured in
the repo's `.acs/settings.json` `release` block, dates the section, and opens
an exempt `release/*` PR for a mandatory human merge.

- **Unhooked** — like `/setup`/`/update`,
  `/acs:release` spawns no subagents, has no `release-state.json`
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
Tickets are the project-management record, so the two product-level
skills, while not running the ticket pipeline, MUST each create their own
**delivery ticket** per run:

- The skill creates the ticket first (type **task**, e.g.
  `SHOP-1 — Product definition (PRD)`): a normal id from the per-repo
  counter, a normal workspace partition, tracker sync when configured (so
  PRD and architecture work is visible in GitHub Projects), and
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
  (which takes the PRD as its primary input). Re-running **amends the PRD in
  place**, preserving sections it does not touch.
- For a **greenfield** product: elicits the definition from the user. For
  an **existing** product: reverse-engineers a baseline PRD from the
  codebase and docs, confirming open points with the user.
- Produces the PRD doc set in the consumer repo wherever the repo already
  keeps its PRD — found through `CLAUDE.md` and the repo, not a setting
  ([ADR-0102](../../architecture/adr/0102-documents-are-found-not-configured.md)) — else at `docs/product/`
  ([configuration.md](configuration.md#document-and-workspace-locations)):
  - `prd.md` — vision, problem statement, target users & personas, goals
    with **measurable success metrics**, prioritized features (e.g.
    MoSCoW), product-level NFRs, constraints & assumptions, out-of-scope;
  - `roadmap.md` — milestones/phases mapped to intended epics, plus a
    **"Release versions"** mapping table (each release version → its
    milestone/wave and the epic(s) it delivers).
- Reflection cycle (survey → author → review — ADR-0109):
  `create-prd-surveyor` (iteration 1 only: mode, outline, open questions),
  `create-prd-author`, `create-prd-reviewer`. The reviewer checks: all required sections
  present, features trace to goals, success metrics are measurable,
  nothing contradicts the stated constraints, and every roadmap milestone
  resolves to exactly one release version (0 orphan milestones) — plus a
  deterministic `structure` floor (declared `required_sections`, blocking)
  and a blocking `audience-style` check (declared audience/style profile; an
  unwaived audience-mismatch blocks, a `clarify.py --source assumption` waiver
  makes it `severity="info"`, non-blocking).
- **Independent corroboration (MAR-304).** The authoring notes additionally record
  three sections (`iter-<n>-authoring.md`) that the
  deterministic floor parses: `## Code evidence`
  (brownfield/amend only, one citation per brownfield code claim in the
  house grammar; `N/A — greenfield, no code to cite` in greenfield),
  `## Answer fidelity` (one line per `clarifications.json`
  answered/assumed entry, naming a verbatim anchor in `prd.md`/`roadmap.md`,
  or an `N/A: <why>` escape), and `## Roadmap milestones` (one line per
  declared milestone, its verbatim `roadmap.md` heading text). The
  reviewer's `Plan conformance` dimension runs the shared deterministic
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
- The surveyor's survey also runs the shared ADR-0012 design-time
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

Purpose: bootstrap and regenerate the product's **high-level design (HLD)** —
the living system view the whole pipeline designs and verifies against. The
low-level design (`lld/<feature>/`) is written per ticket by the Design skills,
not here ([ADR-0121](../../architecture/adr/0121-create-architecture-writes-the-hld-only.md)).

- Product-level and **ticket-independent**: not part of the per-ticket
  pipeline. Run once when starting a product (or onboarding `acs` onto an
  existing repo); re-run to regenerate after major shifts.
- MUST take the **PRD** as its primary input — the skill locates it at
  Start ([ADR-0102](../../architecture/adr/0102-documents-are-found-not-configured.md)).
  With no PRD it does not stop: it works from the run's subject — a document
  named in its arguments, else the user's focus notes plus the codebase —
  and confirms the goals, NFRs and constraints it designs to through the
  clarification ledger, saying in its report that no PRD existed. For an
  **existing codebase** it additionally
  reverse-engineers the current architecture from the code and docs,
  confirming open points with the user; for a **greenfield** product it
  designs the system to satisfy the PRD.
- Produces the doc set in the **consumer repo** wherever the repo already
  keeps it, else at `docs/architecture/`
  ([configuration.md](configuration.md#document-and-workspace-locations)),
  writing only its `hld/` part: the three always-on documents plus one file
  per HLD type the repo enabled at `/acs:setup` (`design.hld_types`,
  [ADR-0120](../../architecture/adr/0120-design-document-catalog-and-ticket-features.md)):
  - `hld/overview.md` — system context, goals, quality attributes,
    constraints (always);
  - `hld/tech-stack.md` — languages, frameworks, conventions (always);
  - `hld/cross-cutting.md` — the conventions every feature's low-level
    design follows: API, data, the event envelope, security, observability,
    configuration (always);
  - `hld/c4-context.md`, `hld/c4-container.md`, `hld/c4-component.md` — the
    **C4 model, levels 1–3**; C4 level 4 (code) is deliberately out of
    scope — the code and its API docs serve that level;
  - `hld/data-model.md` — the conceptual model: entities and relationships,
    no attributes;
  - `hld/integration-map.md` — the API landscape: who exposes and consumes
    which API, sync or async, versioning and auth strategy;
  - `hld/deployment.md` — runtime and infrastructure topology;
  - `hld/project-structure.md` — the intended repo layout derived from the
    C4 container/component views, the canonical target a repo's structure
    is reviewed against;
  - opt-in: `hld/data-flow.md` (trust boundaries, for threat modelling) and
    `hld/capability-map.md`.
- MUST NOT create or change anything under `lld/`; on a re-run, a file for a
  type the repo no longer enables is left as it is.
- All diagrams are **Mermaid** (C4, ER, flowchart and mindmap as code:
  diffable, reviewable, rendered by GitHub, maintainable by agents).
- Runs the Reflection cycle as author → review (ADR-0109) —
  `create-architecture-architect`, `create-architecture-reviewer` — with
  parallel write architects, one per HLD file group (`write-context`,
  `write-structure`, `write-data`, `write-conventions`, only the groups with
  a file to write), all writing from the survey's notes that pin the shared
  vocabulary, and ONE integration architect that runs alone only when a write
  slice reports a seam ([ADR-0125](../../architecture/adr/0125-parallelism-in-skills.md)),
  after an optionally sliced survey, and a
  `create-architecture-gap-analyst` (survey kind) beside it. The reviewer checks:
  the design **satisfies the PRD** (goals, product-level NFRs,
  constraints); the docs match the actual codebase; they are internally
  consistent, one container/component vocabulary across every HLD file;
  diagrams agree with the prose — plus a deterministic `structure` floor over the
  prose-structured files (declared `required_sections:<file>`, blocking)
  and a blocking `audience-style` check (an unwaived audience-mismatch blocks;
  a `clarify.py --source assumption` waiver makes it `severity="info"`,
  non-blocking).
- The architect's survey also runs the shared ADR-0012 design-time
  doc-consistency step, surfacing gap/staleness findings through the
  existing clarification ledger.
- **Gap analysis** ([ADR-0122](../../architecture/adr/0122-design-versions-and-gap-detection.md)): when `hld/` already holds documents,
  the skill MUST spawn one `create-architecture-gap-analyst` per survey area
  in the same message as the survey, and join their notes into
  `iter-1/gaps.md`. Every gap is classified and cited on both sides —
  **undocumented** (in the code, not the HLD) is documented as built;
  **unimplemented** (in the HLD, not the code) is kept and marked planned
  (dashed `planned` style, "(planned)" in prose); **drifted** (both,
  disagreeing) MUST be asked in the survey's one grouped clarification ask
  with both readings, never resolved silently either way. The architect
  MUST handle every gap and the reviewer MUST treat an unhandled or silently
  dropped gap as blocking. A greenfield repo, or one with no HLD yet, skips
  the gap analysis and says so in the report.
- **Design versions** ([ADR-0122](../../architecture/adr/0122-design-versions-and-gap-detection.md)): every HLD file it writes MUST carry
  version front matter (`status`, `version`, `tickets`), set only through
  `acs.py design` — `design init --ticket <delivery-ticket>` for a new file
  (`--status implemented` when it documents the code as built, `proposed`
  when it designs ahead of it), `design bump --ticket <delivery-ticket>` for
  a changed one (re-opened as `proposed`); a file the run leaves unchanged
  keeps its block. The reviewer runs `acs.py design check` on every in-scope
  file.
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

## `/acs:audit-design` (product-level, read-only)

Purpose: report where the system design and the code disagree — the HLD and
every `lld/<feature>/` document, or one feature's, compared with the
implementation ([ADR-0122](../../architecture/adr/0122-design-versions-and-gap-detection.md)).

- MUST be **read-only**: it MUST NOT edit a design document, the code, or
  anything else in the repo. The Design skills fix the design and the
  Development skills the code; its report is what they start from.
- MUST locate the architecture set at Start (documents are found, not
  configured — [ADR-0102](../../architecture/adr/0102-documents-are-found-not-configured.md));
  with none, it MUST say so, point at `/acs:create-architecture`, and stop.
- Takes a scope: a feature slug (`hld/` plus `lld/<slug>/`), `hld` (the HLD
  only), or `all` / nothing (the HLD and every `lld/<feature>/`).
- Is **hooked** but **ticket-independent**: not a step of `ship.yaml` and
  with no subject brake, so its pre-hook checks only that the settings
  resolve, and it runs over its prompt rather than a ticket; it creates no
  delivery ticket and opens no PR.
- MUST read each in-scope document's version front matter with
  `acs.py design check`; a document with no or invalid front matter is itself
  a finding (`unversioned`).
- MUST spawn the gap analysis as `audit-design-gap-analyst` (survey kind) —
  one per disjoint top-level code area, else one over the repo — in one
  message, at most `settings.parallel.max_agents` per wave, and join their slice notes with
  `acs.py notes merge` into `iter-1/gaps.md`; it MUST NOT compare the docs to
  the code itself.
- Every gap MUST be classified **unimplemented** (designed, not built),
  **undocumented** (built, not designed) or **drifted** (both, disagreeing),
  and cited on both sides. An unimplemented element in a `proposed` or
  `approved` document MUST be reported as **planned** — the design ahead of
  the code, not a defect; in an `implemented` document it is a regression.
  Undocumented and drifted gaps are gaps whatever the status.
- Asks nothing during the audit; at the end it MUST offer ONE grouped interaction
  of which gap groups to ticket, record the answer in the clarification
  ledger before acting on it, and on a yes run `/acs:create-ticket` once per
  chosen group. Unable to reach the user, it tickets nothing and says so.
- MUST write its report, `steps/audit-design/iter-1/report.md`, from the
  report template — the repo's `.acs/templates/audit-design-report.md` when
  present, else the built-in `templates/audit-design-report.md` — keeping
  every `## ` section in the template's order, one `### ` entry per gap
  ([ADR-0123](../../architecture/adr/0123-audit-phase-and-audit-security.md)).
  The post-hook MUST refuse a completed audit whose report breaks the template.
- Is an **Audit** skill (ADR-0123): it runs without a ticket — `acs step
  start` opens (or resumes) a run over the invocation and the post-hook
  concludes it.
- Ends with the standard completion report; its `result.json` `states.audit`
  carries the scope, the report path and the count per gap kind — counts the
  post-hook derives from the report's sections, overwriting what the result
  document claimed.

## `/acs:audit-security` (read-only, report-only)

Purpose: find the repository's security weaknesses and report them, ranked by
severity, each surviving an attempt to refute it
([ADR-0123](../../architecture/adr/0123-audit-phase-and-audit-security.md)).
`/acs:review-code`'s security lens judges one changeset's hunks; this audit
judges the repository.

- MUST be **read-only and report-only**: it MUST NOT edit code, a document or
  configuration, MUST NOT file a ticket, MUST NOT emit SARIF, and MUST NOT run
  an exploit, a network scan or any request against a deployed system. The
  Development skills fix what it finds.
- Is an **Audit** skill: **hooked** but **ticket-independent** — not a step of
  `ship.yaml` and with no subject brake; `acs step start` opens (or resumes) a
  run over the invocation and the post-hook concludes it. It asks nothing and
  offers nothing.
- Takes a scope — a path, or `all` / nothing for the repository — and
  optionally a comma list narrowing the categories.
- MUST audit four categories, each by its own `audit-security-auditor`
  (survey kind) spawned in parallel, at most `settings.parallel.max_agents` per wave: `code` (OWASP Top 10
  weakness classes, each finding with its CWE — one auditor per disjoint
  top-level code area, else one), `secrets-config` (hard-coded credentials and
  insecure configuration, CI included), `dependencies` (when a manifest or
  lockfile exists) and `threat-model` (the code against `hld/data-flow.md` and
  `hld/cross-cutting.md`, when the architecture set has either). A category
  whose condition fails MUST be recorded as skipped, with the reason.
- MUST examine dependencies **only through the scanners the repo already has
  installed**: it MUST NOT install a scanner or a dependency, MUST NOT change a
  lockfile, and MUST NOT name a CVE from memory — a known-vulnerable version is
  a finding only with the scanner output that names it.
- MUST give **every** candidate finding, after de-duplicating exact repeats
  only (the same CWE at the same `file:line`), exactly **one** fresh-context
  `audit-security-adjudicator` (judge kind) that sees only that finding — not
  the other findings, not which auditor raised it — is prompted to refute it,
  and defaults to **refuted** when uncertain. Its verdict is `confirmed` (with
  the adjudicated severity and a `resolved_when`), `needs-context` (carried as
  advisory, never dropped) or `refuted` (counted, its reason kept). Two
  auditors raising one weakness MUST NOT confirm it; the adjudication is the
  only filter.
- MUST write its report, `steps/audit-security/iter-1/report.md`, from the
  report template — the repo's `.acs/templates/audit-security-report.md` when
  present, else the built-in `templates/audit-security-report.md` — from the
  auditor reports and the adjudication files only, keeping every `## ` section
  in the template's order: scope and coverage, a summary, the confirmed
  findings by severity (`critical` → `low`, each with CWE, `file:line`,
  evidence, exploit scenario, fix guidance and `resolved_when`), advisory, and
  refuted. The post-hook MUST refuse a completed audit whose report breaks the
  template.
- MUST report a category it could not examine as **uncovered**, never as
  clean.
- MUST NOT write a secret's value in the report, the result, an agent's
  record or any message: only its location, its kind and a redacted form (the
  first 4 characters and the length).
- Ends with the standard completion report; its `result.json` `states.audit`
  carries the scope, the report path, the confirmed counts per severity,
  `advisory`, `refuted`, the scanners run and the slices skipped — the counts
  derived by the post-hook from the report's sections, overwriting what the
  result document claimed.

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
  before proceeding. MUST propose the ticket's `features` — the slugs of the
  PRD features it traces to (`acs.py slug --text "<feature name>"`), which
  name its `lld/<feature>/` design folders — and record the confirmed list
  ([ADR-0120](../../architecture/adr/0120-design-document-catalog-and-ticket-features.md)).
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
  `settings.json`, the ticket syncs **two-way** with a **GitHub Project**:
  - `ticket.json` MUST hold a mapping field linking the local ACS id to the
    remote key (e.g. GitHub `#456`); the local `<ticket-id>` always names
    the workspace partition.
  - Tracker access goes through the official **`gh`** CLI, the only tracker
    transport, which handles authentication itself.
- MUST persist the ticket (and its `<ticket-id>`) into the workspace; the
  `<ticket-id>` names the workspace partition for the whole pipeline.
- Inline shape (MAR-55 invariant (b)): the coordinator runs apply-work
  directly from `references/materialize.md` and spawns no subagent. Correctness is gated by
  schema validation and the user-confirmation gate (`docs_only`, and the
  child breakdown in a `--fan-out` run), not an in-skill reviewer.
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
  executable code under the flag is a blocking review finding.
- MUST NOT classify the ticket's rigor. `/create-ticket` used to capture a
  `size` and a `stakes` axis (MAR-56) and derive a `lane` from them; ADR-0095
  retired all three. Rigor is now ONE judgement, made once, by `/ship`, from
  the implementation plan — the first artifact that says what the change
  actually is, rather than what a request sounded like before anyone read the
  code. `ticket.json` therefore carries no `size`, `stakes` or `lane` field,
  and a ticket that still has them from an older build is read as if it did
  not (`docs/architecture/adr/0095-static-delivery-path-routing.md`).
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
  (`docs/tickets/<ID>/`) — the designer drafts it
  under `steps/create-design/` and the coordinator publishes the reviewed
  bytes — with required sections:
  **context & constraints (incl. NFRs such as security and performance),
  options considered, decision & rationale, architecture (components,
  interfaces/contracts, data model, and Mermaid sequence diagrams for new or
  changed flows), impact & risks, rollout/migration**.
- Child tickets of an epic do NOT repeat design: their `/code` reads
  the **parent epic's** `design.md` (cross-partition read,
  [workspace-and-state.md](workspace-and-state.md)).
- The `create-design-design-reviewer` checks: alternatives genuinely weighed,
  consistency with the existing codebase and docs (including conformance
  with the repo's `standards/` doc set when it has one),
  feasibility, NFR coverage, and a deterministic `structure` floor
  (declared `required_sections`, **configurable** via
  `formats.design_template` / `enforcement.design_sections` — byte-identical
  to the built-in default when unset) — all findings block, including a
  blocking `audience-style` check (declared audience/style profile; an unwaived
  audience-mismatch blocks, a `clarify.py --source assumption` waiver makes it
  `severity="info"`, non-blocking) — same 3-iteration reflection cap.
- Subagents: `create-design-designer`, `create-design-design-reviewer`
  (design → review — ADR-0109).
- The designer's survey also runs the shared ADR-0012 design-time
  doc-consistency step, surfacing gap/staleness findings through the
  existing clarification ledger.
- The design's accepted decision records are committed into the consumer
  repo's ADR folder (found in the repo, else `docs/architecture/adr/` —
  [configuration.md](configuration.md#document-and-workspace-locations)) by
  `/code` as part of its documentation updates.

## /acs:create-data-design

Purpose: write a ticket's **data low-level design** — the logical ERD and the
physical schema of the PRD features it traces to — before implementation
([ADR-0126](../../architecture/adr/0126-lld-data-design-and-flows.md)).
Design-phase work, run by the SA or Tech Lead on a ticket.

- A ticket-scoped Design skill (`PLANNING_SKILLS`, beside `/create-design`):
  hooked, takes no run position, and runnable on its own at any time before
  implementation. Input: the ticket, its `analysis.md` and `design.md`, the
  HLD (`hld/data-model.md`, `hld/cross-cutting.md`, `hld/tech-stack.md`,
  `hld/c4-container.md`), the feature's `api/` documents and its existing
  `data/` documents, each read when present; else the ticket and the code's
  real schema.
- MUST write **documents only** — never source, migration code, DDL scripts,
  ORM models or machine-readable schema files; the physical schema's
  **Migration outline** is ordered prose, never code.
- MUST write only the types it owns that `design.lld_types` enables —
  `logical-erd.md` (entities, attributes, keys, cardinalities; database-agnostic)
  and `physical-schema.md` (tables or collections, column types, indexes,
  constraints, migration outline), both Mermaid `erDiagram`. A disabled type is
  never written; neither enabled → the run completes with nothing written.
- MUST write only inside the ticket's feature folders,
  `<architecture_dir>/lld/<feature>/data/` for each of the ticket's `features`
  (proposed through `acs.py slug` and confirmed in the grouped ask when the
  ticket has none), plus the feature's `README.md` and its row in
  `lld/README.md` when absent — never `api/`, `flows/` or `hld/`.
- The two documents describe ONE model and MUST agree: one designer writes both,
  so there is no integration pass.
- MUST version every document through `acs.py design` — `design init --status
  <proposed|implemented> --ticket <id> --feature <slug>` for a new file,
  `design bump` for a changed one (ADR-0122); elements designed but not built are
  marked planned.
- MUST run gap analysis when the feature already has `data/` documents: one gap
  analyst per survey area in the same message as the survey; undocumented →
  documented as built, unimplemented → kept and marked planned, drifted → a
  question in the ONE grouped ask.
- The reviewer runs as three slices (model, conventions, form) beside the $0
  checks (`acs.py design check`, `mermaid_lint.py`, `structure_lint.py`); any
  blocking finding blocks; same 3-iteration reflection cap.
- MUST NOT commit on the default branch: with no ticket branch checked out it
  records every path it wrote in its result's `states.files`, and
  `/analyze-requirements`' publish commits exactly those files with the ticket's
  docs folder.
- Subagents: `create-data-design-designer` (write), `create-data-design-gap-analyst`
  (survey), `create-data-design-reviewer` (judge).
- States: `feature`, `files`, `types`, `gaps` `{undocumented, unimplemented,
  drifted}`, `entities`.

## /acs:create-flows

Purpose: write a ticket's **behaviour low-level design** — its flows and the
state machines of the entities they change, and, when enabled, its component
detail — before implementation
([ADR-0126](../../architecture/adr/0126-lld-data-design-and-flows.md)).

- A ticket-scoped Design skill (`PLANNING_SKILLS`, beside `/create-design`):
  hooked, takes no run position, runnable on its own. Input: the ticket, its
  `analysis.md` and `design.md`, the HLD, and the feature's `api/` and `data/`
  documents — participants, operations and entities are named as those name
  them — each read when present.
- MUST write **documents only** — never source or machine-readable contracts.
- MUST write only the types it owns that `design.lld_types` enables: `sequence`
  and `activity` (`flows/<flow>.md`, one file per flow, the activity only where
  the flow branches on business rules), `state` (`flows/state-<entity>.md`, one
  per entity whose lifecycle the ticket touches), and the opt-in
  `component-detail` and `class` (`components/<component>.md`). All Mermaid.
- MUST write only inside the ticket's feature folders,
  `<architecture_dir>/lld/<feature>/flows/` and `components/` (plus the feature
  README and its `lld/README.md` row when absent) — never `api/`, `data/` or
  `hld/`.
- MUST write in **parallel slices**, every file in exactly one: one writer per
  flow group, `write-states` for the state machines, `write-components` for the
  components, spawned in one message within `parallel.max_agents`. A name or
  event a slice needed that another slice owns is reported as a **seam**; an
  `integration` pass runs ONLY when a slice reported a seam, reconciling only
  those seams (ADR-0125's pattern).
- A sequence message that changes an entity's state MUST be a transition in
  that entity's state machine, and every transition MUST be triggered by a
  sequence message or a named external event; a reference to an `api/` or
  `data/` document that does not exist yet is an `info` finding, not a failure.
- MUST version every file through `acs.py design … --feature <slug>`, run gap
  analysis over existing `flows/` and `components/` documents beside the survey,
  and ask once in a grouped ask — as `/create-data-design` does.
- Delivery as `/create-data-design`: recorded in `states.files`, committed by
  `/analyze-requirements`' publish.
- Subagents: `create-flows-designer` (write), `create-flows-gap-analyst`
  (survey), `create-flows-reviewer` (judge — three slices: agreement,
  references, form).
- States: `feature`, `files`, `types`, `gaps`, `flows`, `state_machines`.

> **Section numbering.** The numbers below are stable identifiers for these
> per-skill blocks, not the run order. The order the Build/Test/Ship steps
> run in is declared in `plugins/acs/workflows/ship.yaml`
> ([workflow.md](workflow.md#pipeline)); the lettered sections (2a–2d, 3a)
> are the Build/Test skills added by the skills-independence refactor, which
> land between the originally-numbered ones.

## 2a. `/analyze-requirements`

Purpose: the first Build step — understand the ticket against the product
docs and the codebase before anything is planned, make its requirements clear
with the user, and say plainly whether it is ready to plan.

- Input: the ticket, the PRD / requirements / architecture doc sets, the
  codebase, the clarification ledger and the previously published
  `analysis.md`, each read when present. Pre-hook check: the ticket resolves. Brake: an **epic** is
  refused (epics are designed and fanned out, never implemented).
- MUST run three stages, in order (2026-09-27):
  1. **Impact — survey the codebase.** The survey MUST be separate from the
     DRAFT pass and runs as parallel lanes the controller names (ADR-0114):
     the analyst's requirements lane (`pass` = `requirements`) and one
     `acs:analyze-requirements-impact-analyst` lane per code area, which
     derives the impact map from the CODE. Lanes write only authoring notes,
     never the draft; the analyst's synthesis pass merges them into
     `iter-1/authoring.md`. When a published analysis
     exists the survey MUST start from it — re-verify each impact row against
     the current code (still true / changed / gone), carry forward the
     answered `C-n` entries, and record `## Changes since the last analysis`.
     The notes MUST end with `## Questions for the user` in four groups:
     (a) open questions the code and docs cannot answer, (b) conventional
     defaults phrased "Assumed: <default> — confirm or correct",
     (c) proposed refined acceptance criteria, (d) a needs_design
     recommendation and any `features` correction (ADR-0120). Researchable facts are never questions. A survey sliced
     by repo area MUST be reconciled, after `acs.py notes merge` and before
     any question is asked, by one SYNTHESIS pass (`slice="synthesis"`) that
     records `## Synthesis`, turns an unsettled contradiction into a
     group-(a) question and de-duplicates the questions; its file is joined
     last into the notes. An unsliced survey skips it.
  2. **Clarify — make the requirements clear with the user.** After the
     ledger check (recorded answers are never re-asked), every remaining
     question from all four groups MUST be asked in ONE grouped
     AskUserQuestion, conventional defaults included, as confirmations. Each
     answer is its own `clarify.py add` entry. Confirmed refined criteria and
     a confirmed `needs_design` MUST be written into the ticket through
     `acs.py ticket save` (a PATCH), so every later skill plans from the
     clarified ticket; a rejected proposal is recorded and not applied. At
     most ONE follow-up grouped round; anything still open after it is a
     blocker. No questions → the stage is skipped, and the report says so.
     Only when the user is unreachable (a non-interactive run with no answers
     relayed) is a conventional default recorded `--source assumption` with
     a rationale, stated in `## Assumptions`, with `ready_for_planning: true`
     kept; unanswered criterion and needs_design proposals stay open ledger
     entries and the ticket's own criteria are left as written.
  3. **Store — write, review and publish for reuse.** One un-sliced DRAFT pass
     (`pass` = `draft`) writes the analysis from the reconciled notes and the
     recorded answers; the impact reviewer judges it (analyse → impact
     review, at most 3 rounds); the coordinator publishes it and commits the
     ticket's docs folder on the ticket branch — plus the `lld/` files the
     ticket's completed `/create-data-design` and `/create-flows` runs recorded
     in their result's `states.files` (only existing files inside the checkout
     under an `lld/` directory; read from the recorded results, never asserted
     — ADR-0126). A reviewer finding that is a
     new question for the user goes back through Stage 2.
- MUST write `analysis.md` to the ticket's docs folder with front matter
  `{ticket, ready_for_planning, api_surface, needs_design_recommendation}`
  and the sections: Problem restated; Impact
  map (components/files/tests likely touched); Questions; Assumptions;
  Risks; Refined acceptance criteria; Verdict. `## Questions` lists every
  `C-n` with its answer or status, `## Refined acceptance criteria` states
  which criteria were confirmed into the ticket, and `## Assumptions` holds
  only what the user did not answer.
- The published `docs/tickets/<ID>/analysis.md` is the reusable record:
  `/create-impl-plan`, `/create-api-contract` and `/create-test-docs` read it,
  and the next run of this skill starts from it. It falls back to the
  workspace partition only when there is no checkout.
- The impact reviewer MUST check that every `## Questions for the user` item
  was answered in the ledger or carried as an open/assumed entry, and that
  every criterion the analysis marks confirmed matches the ticket.
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
- Subagents: `analyze-requirements-analyst` (requirements lane, synthesis and
  draft passes), `analyze-requirements-impact-analyst` (one code-impact lane per
  area — ADR-0114), `analyze-requirements-impact-reviewer` (analyse → impact
  review — ADR-0109). The loop is run by `acs.py analysis next` / `record-*` /
  `publish` (ADR-0114).
- State file: `analyze-requirements-state.json`; states `ready_for_planning`,
  `api_surface`, `questions_open`.

## 2b. `/create-impl-plan`

Purpose: `/code`'s plan phase, carved out whole into its own skill, ending in
an approved `plan.md`.

- Input: the ticket, `analysis.md` and `design.md` when present (the API
  contract comes *after* the plan — the plan is what names the API surface
  to build); with neither, the ticket alone. Pre-hook check: the ticket
  resolves. Brake: an epic is refused.
- MUST keep every mechanism the phase had inside `/code`, unchanged: the
  survey (the former planner charter, carried by the `planner` role), the
  spec fold, the executor file map, plan approval
  (`standard`/`complex` only, run by those legs) and the plan-revocation path
  (`plan-superseded-<k>.md` in the workspace).
- MUST write `plan.md` to the ticket's docs folder (`docs/tickets/<ID>/`).
  It is always authored by the planner:
  the ADR-0074 fast path, on which the coordinator authored the plan itself
  with no subagent spawn, went with the lanes it forked on (ADR-0095). The
  plan-reviewer judges every draft, and on blocking findings the planner authors
  the remediation (ceiling 3
  review rounds — ADR-0074's 2026-09-14 amendment), so a fixable draft does
  not fail the run on its first verdict.
- MUST plan against the ticket as written when `analysis.md` says
  `ready_for_planning: true`: the ledger entries `/analyze-requirements` left open
  alongside that verdict (refined-criteria and missing-criterion proposals)
  are carried in the plan's Risks as `C-<n> open — planned as written`, never
  re-asked and never a `needs_input` — the analysis skill's own contract
  ("with no user answer … `/acs:create-impl-plan` plans against the ticket as
  written"). Only the plan's own genuine ambiguities and the oversize
  question are asked.
- Subagents: `create-impl-plan-planner`, `create-impl-plan-plan-reviewer`
  (plan → review — ADR-0109; the planner's survey inherited the
  `code-planner` charter). The planner runs on the `planner` model tier.
- State file: `create-impl-plan-state.json`; states `plan_path`,
  `plan_approved`, `file_map`.

## 2c. `/create-api-contract`

Purpose: pin the API surface a ticket changes before it is implemented, so
`/code` builds against a contract and `/create-test-docs` derives cases from
it.

- Input: `plan.md`, `analysis.md`, the ticket, the architecture doc set, and
  the repo's existing contract files, wherever the repo keeps them (else
  `docs/api/`), each read when present; with no plan, the ticket's
  acceptance criteria bound the contract. Pre-hook check: the ticket
  resolves. A plan whose contract declares no API surface makes the step an
  evidenced no-op (`no_surface_owed`).
- MUST write `api-contract.md`: every endpoint/command/message the plan adds
  or changes, request/response shapes, error codes, compatibility and
  versioning notes, and examples — each traced to an acceptance criterion
  **and** to a plan item.
- MUST update the repo's machine-readable contract files where the repo
  keeps them (else create them under `docs/api/`), committed on the ticket
  branch.
- Subagents: `create-api-contract-contract-author`, `create-api-contract-contract-reviewer` (author → review — ADR-0109).
- State file: `create-api-contract-state.json`; states `contract_path`,
  `items`, `traced_acs`.

## 2d. `/create-test-docs`

Purpose: turn the ticket's acceptance criteria (plus the plan and the API
contract when they exist) into an explicit, traceable set of test cases,
before any test is written.

- Input: the ticket's acceptance criteria; `plan.md` when present;
  `api-contract.md` when present. Pre-hook check: the ticket resolves.
- MUST write `test-cases.md` with front matter `{ticket, cases}` and a
  table/list of cases: id `TC-n`, traced acceptance criterion, type
  `unit | integration | e2e`, preconditions, steps, expected result, target
  suite/module.
- **Every acceptance criterion MUST be traced by at least one case**; a
  completed run leaves `untraced_acs` empty.
- The e2e-typed rows are the input `/create-e2e-tests` reads, and the count
  of them is what decides whether that step has anything to do.
- Subagents: `create-test-docs-test-designer`, `create-test-docs-trace-reviewer` (design → trace review — ADR-0109).
- State file: `create-test-docs-state.json`; states `cases`, `e2e_cases`,
  `untraced_acs` (MUST be empty on a completed run).

## 3. `/code`

Purpose: implement the run's approved plan in the consumer repo using TDD.

> **`/code` neither plans nor reviews.** The plan phase left for
> `/create-impl-plan` (§2b) and the review left for `/review-code` (§3b).
> What remains is the implementation itself: read the plan, write the tests
> first, write the code, commit on the run's branch. `/code` implements the
> approved `plan.md` and produces none (invoked on its own with no plan, it
> derives an implicit plan from the subject); it writes no verdict and grades
> nothing. The plan charter is the survey of `create-impl-plan-planner.md`,
> and every `code-planner` mention below reads as that planner's survey. When execution finds the plan itself
> wrong, `/code` ends `failed` with `stop_reason: plan_superseded`, which
> `ship.yaml`'s loop routes back to `/create-impl-plan`.

**Plan authoring (folded into `/create-impl-plan` — ADR 0066).** The plan's
author — always `create-impl-plan-planner` — writes the implementation
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
  `create-impl-plan-planner`, written exactly once per run, before `/code`
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
  iteration 2+ the confirmed findings are delivered to the implementer's
  `<context>`; no planner runs between the review and the fix (ADR-0092).
- **Plan approval (MAR-73, slice 3 of MAR-69).** On the **`standard`** and
  **`complex`** delivery paths only, at the leg's Start, `/code` MUST record a
  **deterministic plan-approval verdict**: `plan-approval.py` computes
  `acs_lib.plan_approval_eligible` from the plan artifact's own content plus
  `tests.coverage` and is the **sole writer** of
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
  `tests.coverage` (default 90) from `settings.json` — measured once,
  at the review's gate, never inside an iteration that may be discarded.
- MUST run the tests its change touches, not the full suite: the full suite is
  the review's final gate, run once per iteration beside the review and
  counted on the iteration that survives review. That discipline is safe precisely because the gate is unconditional
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
  `create-impl-plan-planner.md`'s item 4): a touched/added component missing
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
- Subagents: `code-implementer` and nothing else. `/code` ships **no planner**
  (the plan phase moved to `/create-impl-plan`, §2b) and **no verifier** (the
  review moved to `/review-code`, §3b). The four delivery-path legs
  `code-trivial`, `code-small`, `code-standard` and `code-complex` own no
  agents of their own: each spawns this same implementer, and what varies is how
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
  implementers author the e2e tests their tasks declared (same changeset) and run
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
  changeset — not one implementer's output, not one iteration's diff — against
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
    3. **A final gate**, counted only when stage 2 leaves nothing blocking:
       build, lint, the full unit suite, and coverage against
       `tests.coverage`, started as `acs.py job` jobs beside the lenses
       (ADR-0125) and stopped, unread, when findings block. This is the only
       place the full suite runs in the pipeline. A gate failure is a blocking finding of
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
- Subagents: `review-code-lens` and `review-code-adjudicator`, both judges.
  They are not a write → judge pair and are not meant to be — the two roles
  fan out independently of each other.

## 3a. `/create-e2e-tests`

Purpose: write the ticket's end-to-end suites from the e2e-typed rows of its
test cases, so the post-code e2e run has something ticket-specific to run.

- Input: the e2e-typed rows of `test-cases.md` and the repo's e2e
  configuration (`settings.tests.e2e`). Pre-hook input
  checks: an e2e suite is configured **and** `test-cases.md` lists at least
  one e2e case — a repo with no e2e layer is refused with a pointer at adding
  `tests.e2e` to `.acs/settings.json`, and `ship.yaml` skips the step for it entirely
  (`when: e2e_configured`).
- MUST write the suites at the repo's configured e2e location, named after
  the ticket, committed on the ticket branch.
- Runs **in parallel with `/docs-sync`** in the default workflow — both need
  only `code` — as two legs in two worktrees
  ([workflow.md](workflow.md#parallel-work)).
- Subagents: `create-e2e-tests-test-writer`, `create-e2e-tests-suite-runner` (write → run — ADR-0109).
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
  `result.json` (`states.docs_updated`), `/code`'s implementer report(s)
  `problems` field, and the final code-verify artifact.
- Subagents: `docs-sync-doc-updater`, `docs-sync-drift-reviewer` (update → drift review — ADR-0109).
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
  directly from `references/publish.md` and spawns no subagent. Correctness was gated
  by the upstream review (`/acs:review-code`); the human checkpoint is the PR review.
- PR title and PR description MUST follow the formats configured in
  `settings.json` ([configuration.md](configuration.md)). The default
  `pr_title` is `{title}` — the plain ticket title, e.g. `Add wishlist
  support` — because the description's `## Ticket` section links the ticket
  (ADR-0105).
- Before the PR is opened, the filled description MUST pass
  `pr-conventions.py check` — exactly what CI will check, that the
  description names its ticket
  ([ADR-0106](../../architecture/adr/0106-ci-checks-the-ticket-link-only.md)), plus two
  template-hygiene scans (no unrendered `{placeholder}`, no leftover
  `<!-- -->` comment).
- The PR targets the repo's **default branch** and MUST carry the **`ACS`**
  label — the label `/merge-pr --pr` reads to tell a pipeline PR from an
  exempt one; CI does not require it (ADR-0106).
- **[ASSUMPTION]** PRs are created ready-for-review (not draft).
- **GitHub-native issue linking (standing behavior, MAR-75):** for a ticket
  synced to GitHub the PR body carries a `Closes #<external.key>` reference (a
  distinct bullet in the `## Ticket` section) so GitHub auto-links and
  auto-closes the issue on merge, in addition to the tracker line. The PR also
  carries the `ACS` label and the milestone when one is used. The
  link bullet is omitted entirely for `local`/unsynced tickets. Independently,
  a `pr_title` that uses `{ticket_ref}` renders the tracker's native reference
  when the ticket is synced (MAR-80); the default `{title}` carries no
  reference at all (ADR-0105).
- **Tracker-metadata fill (standing behavior, MAR-101):** on GitHub tracker
  sync (i.e. `ticket.external.provider == "github"` and the ticket is synced),
  an acs-opened/updated PR carries assignee = PR author (the authenticated
  `gh` user, resolved via `@me`) on both the create and edit paths; the
  ticket-type label alongside the `ACS` label, both created
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
- Product-level delivery tickets (PRD, architecture, doc sets) merge like
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
  directly from `references/merge.md` and spawns no subagent. Correctness was gated
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
