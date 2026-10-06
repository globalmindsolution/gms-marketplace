# Skill Requirements

Thirty skills in total. There is no registry file listing them: a skill is
a **directory** under `plugins/acs/skills/` holding a `SKILL.md`, and that is the
whole of what makes it a skill (§2.4). Nothing declares what a skill reads or
writes, or which group it belongs to, because nothing needs to: each skill
reads what it finds and falls back to the run's subject when an upstream
artifact is absent.

The groups below are a reader's aid, not a structure the code knows about
([ADR-0129](../../architecture/adr/0129-discovery-design-development-regroup.md)):

- **Discovery** — `/acs:create-prd`, `/acs:analyze-requirements` (run on
  its own with no ticket, it analyses a PRD feature, a prompt or an attached
  specification into the feature's living analysis,
  `<prd_dir>/features/<feature>/analysis/` —
  [ADR-0128](../../architecture/adr/0128-requirements-from-any-container.md),
  a folder per [ADR-0133](../../architecture/adr/0133-analysis-is-a-folder-by-bounded-context.md)).
- **Design** — `/acs:create-architecture`, `/acs:create-api-contract`,
  `/acs:create-data-design`, `/acs:create-flows` (the last three write the
  living low-level design,
  [ADR-0126](../../architecture/adr/0126-lld-data-design-and-flows.md),
  [ADR-0134](../../architecture/adr/0134-api-contract-is-a-design-document.md)),
  `/acs:create-tech-design` (the change's hand-off for team review,
  [ADR-0135](../../architecture/adr/0135-create-tech-design.md)). The quality, operations,
  principles and standards doc sets are written by hand: no skill bootstraps
  them since `/acs:create-docs` was removed
  ([ADR-0124](../../architecture/adr/0124-remove-create-docs.md)), and the
  skills that read them find them where the repo keeps them.
- **Development** — `/acs:ship` and the steps it drives:
  `/acs:analyze-requirements` (first, on a ticket or a prompt),
  `/acs:create-impl-plan`, `/acs:create-test-docs`, `/acs:code` and its four delivery-path
  legs, `/acs:review-code`, `/acs:create-e2e-tests`, `/acs:docs-sync`,
  `/acs:run-e2e-tests`, `/acs:create-pr` — plus `/acs:merge-pr`.
- **Audit** — `/acs:audit-design` (the design compared with the code),
  `/acs:audit-security` (the repository's security): read-only, ticketless,
  runnable at any time, each writing a report
  ([ADR-0123](../../architecture/adr/0123-audit-phase-and-audit-security.md)).
- **Utility** — `/acs:setup`, `/acs:update`, `/acs:release`, `/acs:handoff`
  (hands a ticket to a teammate on another machine,
  [ADR-0131](../../architecture/adr/0131-ticket-handoff-between-members.md)),
  `/acs:create-ticket`, `/acs:breakdown-ticket` (breaks an epic, or a story or
  task too large for one PR, into PR-sized children,
  [ADR-0138](../../architecture/adr/0138-breakdown-ticket-and-typed-ticket-authors.md)),
  `/acs:set-doc-status` (approves and moves the status
  of the Discovery and Design documents,
  [ADR-0130](../../architecture/adr/0130-prd-versions-and-set-doc-status.md)). A ticket is one container of requirements, cut when
  the work needs one — after a feature's analysis, again after a design — not
  a phase of its own.

Every skill takes **requirements from any container** — a ticket id,
documents (in the repo, or attached from outside it and copied into the run)
and a prompt, mixed as needed; **no skill requires a ticket**
([ADR-0128](../../architecture/adr/0128-requirements-from-any-container.md)).
A skill reads them from the run (`context.requirements`, `acs.py
requirements show`, `<run>/requirements.md`), never from `ticket.json`;
ticket-only steps (`acs.py ticket save`, tracker sync) run only when there is
a ticket.

The ORDER of the implementation skills is `workflows/ship.yaml`'s list, and
nothing else states it. A run's progress over that list is `run.json`; a
skill's own progress inside a step is `steps/<skill>/state.json`.

The phase a skill sits in is a grouping, not an order. The order the
Development steps run in is declared in
`plugins/acs/workflows/ship.yaml` ([workflow.md](workflow.md#pipeline)), and
**every skill MUST be runnable on its own** — a skill MUST NOT refuse to run
because another skill has not run ([hooks.md](hooks.md)).

Twenty of the thirty are **hooked** (a pre-hook and a post-hook
each): both Discovery skills, all five Design skills, the other eight
Development steps (`/create-impl-plan`, `/create-test-docs`, `/code`,
`/review-code`, `/docs-sync`, `/create-e2e-tests`, `/run-e2e-tests`,
`/create-pr`) and `/merge-pr`, both Audit skills, `/create-ticket` and
`/breakdown-ticket`. Six (`/setup`, `/ship`,
`/handoff`, `/update`, `/acs:release`, `/acs:set-doc-status`) are unhooked and take no position in a
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
  twelve **authoring skills** run a write → judge Reflection cycle over
  their own roles — `create-ticket` (one of epic-author, story-author,
  task-author or bug-author per run, then reviewer — at most two iterations,
  [ADR-0138](../../architecture/adr/0138-breakdown-ticket-and-typed-ticket-authors.md)),
  `analyze-requirements` (analyst, impact-analyst, impact-reviewer),
  `create-prd` (surveyor, author, reviewer),
  `create-architecture` (architect, gap-analyst, reviewer), `create-tech-design` (designer,
  reviewer), `create-data-design` (designer, gap-analyst, reviewer),
  `create-flows` (designer, gap-analyst, reviewer), `create-impl-plan`
  (planner, plan-reviewer), `create-api-contract` (contract-author,
  gap-analyst, contract-reviewer), `create-test-docs` (test-designer, trace-reviewer),
  `create-e2e-tests` (test-writer, suite-runner) and `docs-sync` (doc-updater,
  gap-analyst, drift-reviewer). No skill has
  a plan phase before its writer (ADR-0092). `code` spawns implementers only —
  its review is `/review-code`, which runs lenses and adjudicators. Three
  **apply-work skills** (create-pr, merge-pr, breakdown-ticket) run **inline**
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
- write state **only** inside the workspace (`<workspace>/<repo>/runs/<run-id>/`,
  and a ticket's own partition), and write its human-facing documents only
  in the run's phase folder — Discovery `<prd_dir>/features/<feature>/`,
  Design `<architecture_dir>/lld/<feature>/<ticket-id or run-id>/`,
  Development `<development_dir>/<feature>/<ticket-id or run-id>/` — never
  `docs/tickets/` (ADR-0128; the consumer repo is otherwise touched only
  where the skill's job requires it, e.g. `/code` edits source files) — and
  a per-run document there only when the repo shares run documents; kept
  local, it stays in the run's step folder ("Run documents: shared or kept
  local" below, [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md));
- read configuration from the `.acs` `settings.json`
  ([configuration.md](configuration.md)), and spawn each subagent on the
  model and effort of its role's tier configured there — `planner` for survey
  roles and `create-impl-plan`'s planner, `executor` for write roles,
  `verifier` for judge roles
  ([configuration.md](configuration.md#subagent-models)) (apply-work skills
  run inline and spawn none);
- resolve what it works on before doing anything — this checkout's current
  run, else the sources in its arguments (ticket ids, documents, a prompt) —
  and stop and ask when neither resolves
  ([workflow.md](workflow.md#ticket-context));
- record every requirement Q&A in the **clarification ledger**
  (`clarifications.json` — the ticket partition's for a ticket run, the run's
  own `runs/<run-id>/clarifications.json` for a ticketless one): research first, ask once at the cheapest phase
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

`/create-tech-design` (named `/create-design` until ADR-0135) remains bound
by every clause above despite MAR-77's split of
`acs_lib.PLANNING_SKILLS` out of `acs_lib.WORKFLOW_SKILLS`: it keeps the same
hooked lifecycle — pre-hook gate and post-hook persistence, partition-scoped
state, settings-driven subagent models, the per-ticket clarification ledger,
and the standard completion report. MAR-77 changed only where the skill
sits in `acs_lib.HOOKED_SKILLS`'s internal grouping and in the pipeline order
table; none of its runtime obligations changed. The same holds for `/create-data-design` and
`/create-flows`, which ADR-0126 added to `acs_lib.PLANNING_SKILLS` beside it, and
for `/create-api-contract`, which ADR-0134 moved there from `acs_lib.WORKFLOW_SKILLS`.

### Run documents: shared or kept local

The five **per-run documents** — a Development run's analysis (the
`analysis/` folder, [ADR-0133](../../architecture/adr/0133-analysis-is-a-folder-by-bounded-context.md); `docs where --doc analysis.md` resolves it),
`plan.md`, `test-cases.md`, `tech-design.md` and `api-contract.md` — are either
**shared** (published to the run's phase folder, committed by `/create-pr`)
or **kept local** (left in the run's step folder, `<run>/steps/<skill>/`, in
the gitignored workspace) by a saved choice, `docs.share_run_documents`
([ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)). The **living documents** — the PRD and roadmap, the HLD, the
LLD, a feature's living analysis — are always shared.

Every skill that writes a per-run document (`/analyze-requirements`,
`/create-impl-plan`, `/create-test-docs`, `/create-tech-design`,
`/create-api-contract`) MUST:

- run `acs.py docs where --doc <name>` before its first write of that
  document, and write nowhere else than the `path` it reports;
- when `needs` is non-empty, add those questions to its ONE grouped ask —
  `share`: share run documents in the repo or keep them local, and save that
  for me (`.acs/settings.local.json`) or for the team (`.acs/settings.json`);
  `location`: use the proposed folder, give another repo-relative path, or
  keep documents local — record the answers with `acs.py docs decide`, then
  write;
- when no default is saved and the user cannot be reached (a headless run),
  keep the document local **for this run only**, save nothing, and say so;
- follow a saved choice silently — never re-ask it — and name where each
  document went in its completion report ("kept local (team default)",
  "shared to `docs/development/<feature>/<id>/`");
- never create a docs folder in the repo while `docs where` reports a
  `location` question owed: a publish into the repo while an answer is owed
  exits 2 naming `acs.py docs decide`.

Every skill that writes a living document into a folder that may not exist
yet (`/create-prd`, `/analyze-requirements` run on its own (Discovery),
`/create-architecture`, `/create-api-contract`, `/create-data-design`,
`/create-flows`) MUST run
`acs.py docs where --doc living:prd` or `living:architecture` first and, when
`needs` has `location`, ask the location question alone — living documents
are always shared, so there is no share question.

A local document is read by the later steps of the same run through `acs.py
artifacts show`, travels with the run in a `/handoff`, and never reaches the
working tree, so `/create-pr`'s commit plan never lists it.

### Reading an analysis: README first

An analysis is a folder — `analysis/README.md` plus one file per bounded
context ([ADR-0133](../../architecture/adr/0133-analysis-is-a-folder-by-bounded-context.md)). Every skill that reads one — a feature's
living analysis or a run's own (`/create-impl-plan`, `/create-test-docs`,
`/create-tech-design`, `/create-api-contract`, `/create-data-design`,
`/create-flows`, `/create-architecture`, `/code`, `/create-ticket`, and the
next `/analyze-requirements` survey) — MUST:

- read `README.md` first (`acs.py artifacts show` returns it as
  `artifacts["analysis.md"]` and lists every file of the folder, README
  first, in `analysis_files`);
- then read only the context files its own work needs, chosen from the
  README's contexts table — never load the whole folder by default;
- fall back to a single `analysis.md` where no `analysis/` folder exists (an
  analysis published before ADR-0133, or a legacy
  `docs/tickets/<ID>/analysis.md`), reading it whole as before.

---

## `/setup` (optional)

Purpose: let a team change the branch/commit/PR conventions and install the
CI that enforces them — nothing else. It is **optional**: every setting has a
working default, so no skill needs `/setup` to have run first
([ADR-0105](../../architecture/adr/0105-acs-runs-without-setup.md)). Every other setting
(ticket prefix, coverage target, merge strategy, tracker, models, named test
suites, advisories) keeps its default and is edited by hand in `.acs/settings.json`,
validated against `settings.schema.json`.

- MUST write its conventions only to the project settings file
  (`<repo>/.acs/settings.json`, committed — conventions are the team's);
  they carry no scope question. MUST NOT write a value equal to its built-in
  default, and MUST remove one an earlier run wrote, so the file carries only
  choices.
- MUST show where run documents go and let the user change it
  ([ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)): the saved `docs.share_run_documents` (shared, kept local, or
  not decided yet) and the scope that holds it, and each phase folder with
  its resolution source (`setting`, `discovered`, `default`). A change is
  recorded through `acs.py docs decide` — the share choice in the scope the
  user picks (for me: `.acs/settings.local.json`; for the team:
  `.acs/settings.json`), a folder as `docs.<kind>_dir` in
  `.acs/settings.json`.
- The workspace derives silently to `<main-checkout>/.acs/state-machine` —
  no prompt, no required input, and no override (ADR-0086,
  [ADR-0102](../../architecture/adr/0102-documents-are-found-not-configured.md)).
- When it offers acs's Claude Code permission rules, MUST also offer the
  Bash sandbox write rule for the workspace —
  `{"sandbox": {"filesystem": {"allowWrite": ["<absolute main checkout>/.acs/state-machine"]}}}`
  — so a sandboxed `acs.py write` from a Claude Code worktree session can
  record state. The path MUST be absolute and name the main checkout's
  folder, also when setup runs in a linked worktree, and the rule MUST go to
  the main checkout's `.claude/settings.local.json` — never the committed
  `.claude/settings.json`, even when the permission rules went to the team
  file — merged in place (other keys and entries kept, added once, a re-run
  adds nothing)
  ([ADR-0136](../../architecture/adr/0136-state-is-written-through-acs-write.md)).
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
  be refused with the design-and-breakdown pointer (`/acs:create-tech-design
  <id>` when it has no design, then `/acs:breakdown-ticket <id>`). A `bug`
  ships like a story (ADR-0138). There is no
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

Purpose: hand a ticket in mid-flight from one team member to another, across
machines, with its uncommitted work and its pipeline state
([workflow.md](workflow.md#ticket-handoff),
[ADR-0131](../../architecture/adr/0131-ticket-handoff-between-members.md)).

- MUST offer three modes: `/acs:handoff <ID>` sends, `/acs:handoff receive
  <ID>` receives, `/acs:handoff list` lists the waiting handoffs. The
  deterministic work MUST go through `acs.py handoff send|receive|list`; the
  skill only asks and reports.
- **Send** MUST ask ONE grouped question — the handoff note (done, in
  flight, next, decisions), each outside-repo attachment of the run (include
  or skip, one by one) and confirmation of the push — and MUST NOT package an
  outside-repo attachment the sender did not confirm.
- Send MUST package only the ticket's **resume set**: the uncommitted work
  (ignored files excluded), the ticket and its clarification ledger, the
  run's ledger files and baseline, each step's state, result, current
  artifacts and verdicts, the trees the state cites, the note and a
  manifest, with absolute paths as tokens. It MUST NOT package the rest of
  the `iter-*/` audit trails, `jobs/`, `agents/`, locks, lock events, session
  pointers or logs.
- Send MUST build the package as one commit on the run's `baseline.base_sha`
  through a temporary index — never touching the sender's HEAD, index,
  branches or working tree — and push it to `refs/acs/handoff/<ID>` only;
  it MUST NOT push a branch. It MUST refuse an existing ref unless
  `--replace` (every push carries a lease), an archived ticket and a run
  that is not about a ticket.
- After a send the sender's work, run and lock MUST stay as they were.
- **Receive** MUST refuse a dirty working tree, MUST check the work applies
  with a three-way merge before touching the checkout and stop on a conflict
  with the conflicting paths, MUST
  restore the resume set with local paths, raise `counters.next` to at least
  the sender's, and MUST refuse a local run with the same id unless
  `--replace` (which backs it up first). It MUST delete the remote ref unless
  `--keep-ref`, show the note, and print `continue_with`.
- Not part of the gated pipeline (unhooked); no subagents.
- A phase handoff MUST NOT need this skill: `/acs:set-doc-status`, then
  `/acs:create-pr`, then tell the next team.
- The context-pressure **session pause** — flush the soft context, finalize
  the in-flight step `interrupted` with `stop_reason: context_pressure`,
  release the lock — is not this skill
  ([workflow.md](workflow.md#session-pause)).
- Workflow coordinators SHOULD trigger the same flush proactively on context
  pressure, through `handoff.py`, without waiting for the user.

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

## /acs:set-doc-status (utility)

Purpose: approve, and otherwise move the status of, the versioned Discovery
and Design documents — the PRD, the roadmap, each feature's living analysis,
the HLD, each feature's living LLD and each change's `tech-design.md` — and
record who moved them, when and
why ([ADR-0130](../../architecture/adr/0130-prd-versions-and-set-doc-status.md),
[ADR-0135](../../architecture/adr/0135-create-tech-design.md)).

- **Unhooked and inline** — like `/setup`/`/update`, it spawns no subagents,
  opens no run, runs no `acs step start` and has no pre- or post-hook. It is
  not part of the gated pipeline and takes no position in a run. Edit and
  Write are disallowed to it: it MUST NOT edit a front-matter block.
- MUST list the documents through `acs.py design list` — grouped by phase
  (Discovery: PRD with roadmap, feature analyses; Design: HLD, each feature's
  LLD) and feature, each with its `status`, `version`, `problems` and
  `allowed` moves — and from a run's design-record folder
  (`lld/<feature>/<ticket-id or run-id>/`) MUST list `tech-design.md` only,
  in its feature's Design group, labelled with that ticket id or run id
  (ADR-0135); no other file of that folder is listed.
- MUST NOT offer a document with `problems` (no or an invalid block) or one
  with no `allowed` move (a `deprecated` one); a document with `problems` is
  reported under Findings.
- MUST ask which documents to move in ONE grouped multi-select question — one
  option per group (a feature's analysis, a feature's LLD, the HLD, the PRD
  with its roadmap), each showing every document's status and version, and
  single documents by their path — paging a phase when it has more than four
  groups.
- MUST offer only a target status every selected document either may move to
  (`allowed`) or already has — `approved` first when any is `proposed` — and
  MUST require a reason for `deprecated` (optional otherwise); a selected
  document already at the target is dropped and reported "already
  <status>".
- MUST confirm the exact plan (`<path>: <status> v<version> → <target>`, the
  reason, who is recorded) before it writes, then MUST move every document
  with ONE `acs.py design status --set <status> [--by <name>] [--reason
  <text>] <doc>...` call. The CLI records `status_by` (default `git config
  user.name <user.email>`), `status_at` (ISO-8601 UTC) and `status_reason`,
  never changes `version`, and is **all or nothing**: it validates every
  document (it exists, its block is valid, the transition is legal) before
  writing any, so a refusal leaves every document as it was. The skill MUST
  report a refusal verbatim and MUST NOT retry the documents one by one.
- Arguments skip the asks they answer: a status (or its verb — `approve`,
  `deprecate`, `reopen`), targets (a feature slug — its analysis and its LLD —
  a group, a document path) and `--reason`/`--by`
  (`/acs:set-doc-status approved wishlist`). A target that matches no listed
  document is reported, not guessed at. With no way to ask (a headless
  session) and an undecided request, it changes nothing and prints the
  command that would apply it.
- MUST NOT branch, stage, commit or push
  ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)): it ends
  by listing the changed files and pointing at `/acs:create-pr "<what was
  approved>"`, whose docs-only PR carries the decision for review. Its
  completion report reads **Scope** in the Ticket line's place.
- The move to `implemented` is otherwise `/acs:docs-sync`'s, once its gap
  analyst finds the code matching (ADR-0122,
  [ADR-0137](../../architecture/adr/0137-docs-sync-keeps-the-feature-lld-current.md));
  this skill offers it only where `allowed` does.

## Product-level delivery (no ticket)

The two product-level skills run **without a ticket** and deliver **nothing
themselves** ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)):

- `acs step start --step <skill> --args "<arguments>"` opens a ticketless
  run over the invocation — or resumes this checkout's interrupted one —
  the way the audits do; the post-hook concludes it. No ticket is minted,
  nothing is synced to a tracker, and no branch is created.
- The skill MUST NOT create or switch a branch, stage, commit, push or open a
  PR. Its documents stay as **uncommitted changes** in the working tree, on
  whatever branch is checked out, and every path it wrote is recorded,
  repo-relative, in its result's `states.files`.
- Its final message lists those files and points at `/acs:create-pr
  "<what changed>"`: given a prompt and no current run, create-pr groups the
  uncommitted changes by layer — each doc set its own commit — on a branch of
  their own and opens the PR (labelled `acs-exempt`, since it names no
  ticket); `/merge-pr --pr <n>` lands it after review.
- The skill's state lives in its run's partition like any other skill
  state; locking, resume and handoff work as for any other run.

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
  ([configuration.md](configuration.md#document-and-workspace-locations)),
  a new folder only once the user has confirmed it (`acs.py docs where --doc
  living:prd` reports a `location` question owed, [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)):
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
- **Versioned** ([ADR-0130](../../architecture/adr/0130-prd-versions-and-set-doc-status.md)):
  `prd.md` and `roadmap.md` open with the version front matter of
  [ADR-0122](../../architecture/adr/0122-design-versions-and-gap-detection.md)
  (`status`, `version`, `tickets`, and the approver keys once a status is
  moved). The coordinator MUST run `acs.py design init --status proposed` on a
  new document and `acs.py design bump` on a changed one — a document it left
  unchanged keeps its block and version — and MUST run `acs.py design check`
  on both in its $0 floor, where a missing or invalid block is a finding. The
  author's byte-for-byte preservation rule and the reviewer's
  untouched-content dimension exempt the leading front-matter block; a
  changed document MUST show a bumped version instead — one version per run.
  A `deprecated` PRD is not amended: `design bump` refuses it and the run
  fails. The skill MUST NOT write the block by hand, and MUST NOT approve its
  own output: approval is `/acs:set-doc-status`'s, after review.
- State lives in the run's partition (`steps/create-prd/`).
- Delivery: none of its own — the documents stay uncommitted for
  `/create-pr "<prompt>"` ([product-level delivery rules](#product-level-delivery-no-ticket)).
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
  ([configuration.md](configuration.md#document-and-workspace-locations)) —
  a new folder only once the user has confirmed it (`acs.py docs where --doc
  living:architecture`, [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)) —
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
  `acs.py design` — `design init` for a new file (`--status implemented`
  when it documents the code as built, `proposed` when it designs ahead of
  it), `design bump` for a changed one (re-opened as `proposed`); a file the
  run leaves unchanged keeps its block. The run has no ticket, so no
  `--ticket` is passed. The reviewer runs `acs.py design check` on every in-scope
  file.
- State lives in the run's partition (`steps/create-architecture/`)
  ([workspace-and-state.md](workspace-and-state.md)).
- Delivery: none of its own — the documents stay uncommitted for
  `/create-pr "<prompt>"` ([product-level delivery rules](#product-level-delivery-no-ticket));
  the TDD pipeline does not apply to a docs-only change.
- Maintenance afterwards belongs to the pipeline: `/create-tech-design` designs
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
  name its `lld/<feature>/` design folders and the feature folders its runs'
  documents go to (ADR-0128) — and record the confirmed list
  ([ADR-0120](../../architecture/adr/0120-design-document-catalog-and-ticket-features.md)).
- MUST interact with the user to resolve ambiguities before finalizing
  (clarifying questions).
- **AC/DoD substantiveness gate (standing behavior, MAR-157):** an
  `acceptance_criteria` entry that is not concrete/testable (vague
  satisfaction-claim boilerplate with no observable outcome, e.g. "works
  correctly") is a finding of the draft's reviewer (below), and any entry
  still flagged when the draft reaches the confirmation is surfaced to the
  user; the ticket does not finalize with a flagged entry unless the user
  explicitly confirms it anyway. No new subagent is introduced for this check:
  it is one of the reviewer's dimensions, and in `/breakdown-ticket` the
  coordinator applies it to every proposed child (ADR-0138).
- MUST create a ticket with a type of **epic**, **story**, **task** or
  **bug** ([ADR-0138](../../architecture/adr/0138-breakdown-ticket-and-typed-ticket-authors.md)).
- **Drafting: one type author, then a reviewer (ADR-0138).** The coordinator
  parses the input, applies the sizing rubric that picks the type and asks
  every question in one grouped ask; between the type decision and the
  confirmation it spawns ONE author for the chosen type —
  `create-ticket-epic-author`, `create-ticket-story-author`,
  `create-ticket-task-author` or `create-ticket-bug-author` (write roles that
  write only the draft `steps/create-ticket/iter-<n>/draft.json` and
  `draft.md` through `acs.py write`, and never mint a ticket or touch the
  tracker) — then `create-ticket-reviewer` (judge), which checks that the
  acceptance criteria are concrete and testable, the PRD trace and
  `features`, the type's own completeness, an honest size and that no fact
  is invented. At most two iterations; the user confirms the reviewed draft.
  The rules every type shares — acceptance-criteria quality, PRD tracing,
  features, grounding — live once, in
  `skills/create-ticket/references/authoring-rules.md`; each author carries
  only its own type's template and rules:
  - **epic** — problem and outcome, scope in and out, success metrics, a
    `needs_design` recommendation and a candidate breakdown *outline* only;
  - **story** — the user-facing value (As a / I want / so that, or an
    equivalent) and acceptance criteria in Given/When/Then;
  - **task** — the technical outcome and a done-when checklist, no user story;
  - **bug** — steps to reproduce, expected vs actual behaviour, the
    environment or version, a `severity` (`critical`, `high`, `medium` or
    `low`, separate from `priority`), the suspected area with citations, and
    an acceptance criterion that a regression test reproduces the bug and
    passes after the fix.
- When the ticket type is **epic**, its own creation run mints no children
  and ends with `children: []` and *Next: `/create-tech-design <id>` (when
  `needs_design`) → `/breakdown-ticket <id>`*; `/breakdown-ticket` mints the
  children (below). Each child gets its own `<ticket-id>` and runs its own
  pipeline. The epic's status is auto-managed: **In Progress** when work
  starts on any child, **Done** when all children are merged (see
  [workflow.md](workflow.md#epic-fan-out)).
- `/create-ticket <epic-id> --fan-out` and `/create-ticket split <id>` MUST
  refuse, naming `/acs:breakdown-ticket`, which does what both did (kept for
  one release after ADR-0138).
- Ticket title and description MUST follow the per-type ticket formats
  configured in `settings.json` — epic, story, task and bug each have their own
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
- Materialisation stays inline (MAR-55 invariant (b)): after the user
  confirms the reviewed draft, the coordinator runs the apply-work directly
  from `references/materialize.md` (`new-ticket.py`, `acs.py ticket save`)
  and tracker sync; the authors and the reviewer never mint a ticket.
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
  epic; story/task/bug imports are always `false`). From there the ticket ships
  like any local one.
- Two-way sync runs **on demand** (triggered explicitly by the user or a
  skill); scheduled background sync routines are a later enhancement.
- Sync conflicts (both the local and the remote ticket changed) are resolved
  by **asking the user** which side wins.
- Ticket schema — required fields: **title, type, description, acceptance
  criteria, priority, parent epic, children, status, external mapping,
  assignee, story points, needs-design flag, docs-only flag**. Parent/child links are stored
  in **both directions** (epic lists `children`; each child stores `parent`).
  Optional bug fields, schema-validated strings: **`severity`**
  (`critical`/`high`/`medium`/`low`), **`reproduction`**, **`expected`**,
  **`actual`**, **`environment`** (ADR-0138).
- MUST set **`needs_design`**, epic-only: always `true` for epics (stated,
  not asked); always `false` for stories, tasks and bugs, never offered or
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
- MUST size stories/tasks/bugs to **one reviewable PR** (rule of thumb ~<=400
  changed lines, one concern, grounded in a codebase survey); above the bar the
  coordinator recommends an epic, whose children `/breakdown-ticket` cuts at
  PR-sized, independently shippable seams. Splitting an existing oversized
  ticket is `/breakdown-ticket <id>` too.
- **GitHub-native reconciliation (standing behavior, MAR-75):** on GitHub
  tracker sync (Step 5) the synced issue carries the acs ticket id on its body
  (`acs-ticket: {ticket_id}`, rendered by the type description templates) and
  is filled with every field the target Project schema supports — the `ACS`
  and type labels, the assignee when known, the milestone when the repo uses
  one, and applicable Project fields (Status, Type); a field the schema does
  not define is surfaced, not silently skipped. `local` (unsynced) tickets are
  unaffected.
- **Fan-out tracker sync (standing behavior, MAR-84):** the tracker-sync set
  is the root ticket (unless it is an import) plus **every child minted by
  `/breakdown-ticket`** — no minted child is left unsynced — **EXCLUDING any
  ticket whose `external` is already non-null**, so a breakdown run syncs
  only the newly minted children and never re-creates the already-synced
  root's remote issue as a duplicate; a split's already-synced root has its
  remote issue **updated** instead. Both skills sync through the one
  tracker-sync reference. Product-flow delivery tickets ("Product definition
  (PRD)", "Product architecture doc set" — minted before ADR-0127, none since)
  are excluded from this set and always stay unsynced. A sync failure for any one ticket in the set is
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

## 1a. `/breakdown-ticket` (utility)

Purpose: break one container of work too large for one PR — an epic, or an
oversized story or task — into PR-sized child tickets
([ADR-0138](../../architecture/adr/0138-breakdown-ticket-and-typed-ticket-authors.md)).
It absorbs what `/create-ticket <epic-id> --fan-out` and `/create-ticket
split <id>` did.

- MUST take a ticket id — the epic, story or task it breaks down; documents or
  a prompt beside it join the run's requirements (ADR-0128). The pre-hook
  (`gate_breakdown_ticket`) refuses when no ticket resolves, its partition is
  missing or archived, the ticket is `done`, or it is a `bug` — a defect is
  fixed in one PR; a related bug or task is a new `/create-ticket`.
- MUST read, before proposing anything: the ticket and the run's
  requirements; the feature analysis (its `README.md` and the bounded
  contexts the ticket touches, ADR-0133); the tech design (`acs.py
  artifacts show design` → `tech-design.md`, a legacy `design.md` still
  read, ADR-0135) — deriving the children from its LLD snapshots, the HLD
  views it affects and its rollout order when present, else from the
  ticket's description and acceptance criteria; and, when the run has one,
  the plan's oversize-split signal and the seams it recorded (ADR-0069).
- MUST warn — never block — when an epic's tech design is absent or not
  `approved` (`/set-doc-status approved <feature>`), and go on only with the
  user's go-ahead.
- MUST propose every child in ONE grouped confirmation: title, type
  (`story`, `task` or `bug`), concrete and testable acceptance criteria,
  `features` (the parent's unless narrowed), `needs_design: false`, and a
  size from create-ticket's PR-size rubric. Nothing is minted before the
  user confirms or edits the breakdown.
- MUST mint the confirmed children with `new-ticket.py --parent <id>` — which
  copies the parent's `features` unless `--features` is given — save each
  child's acceptance criteria with `acs.py ticket save`, and sync them to the
  tracker through create-ticket's tracker-sync reference (one copy, shared),
  excluding any ticket already synced.
- A **story or task** being split is first converted to an **epic that keeps
  its id**, description and PRD trace; downstream work already present on it
  requires the user's confirmation first. `new-ticket.py --parent` still
  refuses a parent that is not an epic, so the conversion always comes first.
- Runs **inline**: no subagent, with its own pre- and post-hook (mirroring
  `/create-ticket`'s). It never writes a document into the repo.
- Records `ticket_id`, `type` (always `epic` after the run), `converted_from`
  (the type a split converted, else `null`), `children` (the parent's full
  list), `minted` (this run's children) and `design_status` (the tech
  design's status, or `null` when there is none).
- Ends with the standard completion report; *Next:* each child's own
  pipeline (`/ship <child-id>`).

## 2. `/create-tech-design` *(conditional)*

Purpose: settle the system design before implementation is specified — for
tickets where the change is architecturally significant — and hand it to the
team for review before implementation starts
([ADR-0135](../../architecture/adr/0135-create-tech-design.md); the skill was
`/create-design` until then, and no alias keeps the old name).

- Runs only when the run's requirements carry **`needs_design: true`** —
  refined by `/analyze-requirements`, else the ticket's flag (set for epics
  only; stories/tasks are always `false` and skip straight to `/code`, unless
  they inherit a parent epic's design). A ticketless run with no recorded
  `needs_design` runs it when the user invoked the skill with requirements:
  the invocation is the ask (ADR-0128). The gate is `gate_create_tech_design`
  in `SUBJECT_GATES`; epics are allowed.
- MUST analyze the requirements, the feature's living analysis, the
  codebase, and existing docs; MUST evaluate
  **multiple options with trade-offs** and interact with the user on the
  genuinely open decision points before settling.
- MUST take the product architecture doc set (found in the repo) as
  primary input when it exists: the design either **conforms to the
  documented architecture** or explicitly lists the architecture changes it
  requires — which `/code` then applies to the doc set as part of the
  change.
- Produces **`tech-design.md`** in the run's Design folder
  (`<architecture_dir>/lld/<feature>/<ticket-id or run-id>/`, ADR-0128) — or keeps it in the run's step folder when the repo keeps run documents local ("Run documents: shared or kept local", [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)) — the designer drafts it
  under `steps/create-tech-design/` and the coordinator publishes the reviewed
  bytes — with these sections, in order:
  **Decision & options** (context, options considered, decision & rationale),
  **HLD views affected** (excerpts of the `hld/` views the change touches,
  each linked at its version), **LLD** with **API**, **Data**, **Flows** and
  **Components** (snapshots of the feature's living `lld/<feature>/` documents,
  each linked at its version; "none yet" with the skill that writes it when
  absent), **NFRs**, **Risks** (rollout and migration included) and **Open
  questions**. An epic fills every section; a story or task fills those it
  needs and marks the rest "n/a" with the reason.
- MUST open the document with ADR-0122's front matter (`status: proposed`,
  `version`, `tickets`, `feature`), written only through `acs.py design init`
  for a new file and `design bump` for a revised one. `acs.py design list`
  lists it in its feature's Design group, so the team approves it with
  `/acs:set-doc-status approved <feature>`; the skill's report points there,
  then at `/create-impl-plan`, which states the document's status in its own
  report and warns, without blocking, when it is not approved.
- Every reader resolves `tech-design.md` first and falls back to a legacy
  `design.md` (and an older run's `steps/create-design/`) when it is absent;
  nothing writes `design.md`. The run artifact keeps the key `design`
  (`acs.py artifacts show design`), with `tech-design` an alias.
- Child tickets of an epic do NOT repeat design: their `/code` reads
  the **parent epic's** `tech-design.md` (cross-partition read,
  [workspace-and-state.md](workspace-and-state.md)).
- The `create-tech-design-reviewer` checks: alternatives genuinely weighed,
  consistency with the existing codebase and docs (including conformance
  with the repo's `standards/` doc set when it has one), cross-category
  consistency between the snapshots (an operation a flow names is in the api
  document, an entity it names is in the data document), snapshot freshness
  (each linked version is the document's current version),
  feasibility, NFR coverage, and a deterministic `structure` floor
  (declared `required_sections`, **configurable** via
  `formats.design_template` / `enforcement.design_sections` — byte-identical
  to the built-in default when unset) — all findings block, including a
  blocking `audience-style` check (declared audience/style profile; an unwaived
  audience-mismatch blocks, a `clarify.py --source assumption` waiver makes it
  `severity="info"`, non-blocking) — same 3-iteration reflection cap.
- Subagents: `create-tech-design-designer`, `create-tech-design-reviewer`
  (design → review — ADR-0109). Their models are set under
  `models.create-tech-design` (`designer`, `reviewer`); a saved
  `models.create-design` block is migrated to it on load.
- The designer's survey also runs the shared ADR-0012 design-time
  doc-consistency step, surfacing gap/staleness findings through the
  existing clarification ledger.
- The design's accepted decision records are written into the consumer
  repo's ADR folder (found in the repo, else `docs/architecture/adr/` —
  [configuration.md](configuration.md#document-and-workspace-locations)) by
  `/code` as part of its documentation updates, and committed with the other
  design documents by `/create-pr`.

## /acs:create-data-design

Purpose: write a ticket's **data low-level design** — the logical ERD and the
physical schema of the PRD features it traces to — before implementation
([ADR-0126](../../architecture/adr/0126-lld-data-design-and-flows.md)).
Design-phase work, run by the SA or Tech Lead on a ticket.

- A Design skill (`PLANNING_SKILLS`, beside `/create-tech-design`): hooked, takes
  no run position, and runnable on its own at any time before
  implementation, on a ticket, a feature slug, a prompt or documents — the
  feature comes from the argument, the requirements' features or the ticket,
  and no ticket is needed (ADR-0128). Input: the run's requirements, the
  feature's living analysis, the change's analysis (README first) and `tech-design.md`, the
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
  (always shared; an architecture folder that does not exist yet is
  confirmed first, `docs where --doc living:architecture`, [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md))
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
- MUST be **docs-only in delivery too**: it MUST NOT create a branch, commit,
  push or open a PR. The documents stay as local uncommitted changes, and the
  run finishes by listing every path it wrote, repo-relative, in its result's
  `states.files` (and its completion report); `/create-pr` commits them with
  the ticket's design documents ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)).
- Subagents: `create-data-design-designer` (write), `create-data-design-gap-analyst`
  (survey), `create-data-design-reviewer` (judge).
- States: `feature`, `files`, `types`, `gaps` `{undocumented, unimplemented,
  drifted}`, `entities`.

## /acs:create-flows

Purpose: write a ticket's **behaviour low-level design** — its flows and the
state machines of the entities they change, and, when enabled, its component
detail — before implementation
([ADR-0126](../../architecture/adr/0126-lld-data-design-and-flows.md)).

- A Design skill (`PLANNING_SKILLS`, beside `/create-tech-design`): hooked, takes
  no run position, runnable on its own on a ticket, a feature slug, a prompt
  or documents (the feature from the argument, the requirements or the
  ticket; ADR-0128). Input: the run's requirements, the feature's living
  analysis, the change's analysis (README first) and `tech-design.md`, the HLD, and the feature's `api/` and `data/`
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
  README and its `lld/README.md` row when absent; always shared, an
  architecture folder that does not exist yet confirmed first through `docs
  where --doc living:architecture`, [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)) — never `api/`, `data/` or
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
- Delivery as `/create-data-design`: no branch, commit or PR — local
  uncommitted changes, listed in `states.files`, for `/create-pr` to commit.
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

## /acs:create-api-contract

Purpose: design the interfaces a feature or a change adds or changes —
every endpoint, command or message, its request/response shapes, error
codes, compatibility notes and examples — as living low-level design
documents, before the plan, so `/create-impl-plan` plans against them,
`/code` builds against them and `/create-test-docs` derives cases from them
([ADR-0134](../../architecture/adr/0134-api-contract-is-a-design-document.md)).
Design-phase work, run by the SA or Tech Lead.

- A Design skill (`PLANNING_SKILLS`, beside `/create-data-design` and
  `/create-flows`): hooked, takes no run position — it is not a `ship.yaml`
  step and `/ship` never runs it — and runnable on its own at any time
  before implementation, on a ticket (an epic included), a feature slug, a
  prompt or documents (ADR-0128). No plan is needed or read for tracing.
  Input: the run's requirements (`context.requirements`), the feature's
  analysis (README first, then the contexts it needs), the HLD's
  `integration-map.md` and the API conventions in `cross-cutting.md`, the
  feature's existing `lld/<feature>/api/` and `lld/<feature>/data/`
  documents, and the interfaces in the code, each read when present.
- MUST trace every item to an acceptance criterion; nothing traces to a plan
  item.
- Owns the `api-contract` LLD type: when `design.lld_types` disables it, the
  run completes as a recorded no-op (`outcome: type_disabled`) with nothing
  written, and `states.types` records what was produced.
- MUST write **documents only**:
  - the living `<architecture_dir>/lld/<feature>/api/<interface>.md`, one
    file per interface (a REST resource, a CLI command group, an event topic,
    a gRPC service), each opened with ADR-0122 front matter —
    `acs.py design init --status proposed --type api-contract --feature <f>
    --ticket <id>` for a new file, `design bump` for a changed one. Living
    documents are always shared (an architecture folder that does not exist
    yet is confirmed first, `docs where --doc living:architecture`);
  - the per-run record `api-contract.md` in the run's Design folder
    (`<architecture_dir>/lld/<feature>/<ticket-id or run-id>/`, ADR-0128) — or
    kept in the run's step folder when the repo keeps run documents local
    ("Run documents: shared or kept local",
    [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md))
    — summarising the change and linking every interface file at its version.
- MUST NOT create or edit the repo's machine-readable contract files
  (OpenAPI, JSON Schema, proto, AsyncAPI): `/create-impl-plan` plans them from
  the approved contract and `/code` makes them.
- MUST run gap analysis when the feature already has `api/` documents: one
  `create-api-contract-gap-analyst` per existing interface document, in the
  same message as the survey, every gap between the document and the code
  classified unimplemented, undocumented or drifted, cited on both sides
  (ADR-0122); undocumented → documented as built, unimplemented → kept and
  marked planned, drifted → a question in the ONE grouped ask.
- The contract-author writes in slices, one per interface, with an
  integration pass only when a slice reports a seam (ADR-0125); the reviewer
  judges beside the $0 checks (`acs.py design check` on every written api
  document, `mermaid_lint.py`, `structure_lint.py`); same 3-iteration
  reflection cap.
- MUST NOT branch, commit, push or open a PR: every path it wrote is listed,
  repo-relative, in `states.files`, and `/create-pr` commits them in its
  `design` layer ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)).
- Subagents: `create-api-contract-contract-author` (write),
  `create-api-contract-gap-analyst` (survey),
  `create-api-contract-contract-reviewer` (judge).
- State file: `create-api-contract-state.json`; outcome `contract_written`,
  or `type_disabled` when the type is off; states `contract_path`,
  `feature`, `files`, `types`, `interfaces`, `items`, `traced_acs`, `gaps`
  `{undocumented, unimplemented, drifted}`.

## 2a. `/analyze-requirements`

Purpose: understand a change's requirements against the product docs and
the codebase before anything is designed or planned, make them clear with the
user, and say plainly whether they are ready to plan. It works in two phases
([ADR-0128](../../architecture/adr/0128-requirements-from-any-container.md),
[ADR-0129](../../architecture/adr/0129-discovery-design-development-regroup.md)):

- **Discovery** — run on its own, with no ticket: a PRD feature, a prompt,
  PRD documents or an attached specification are analysed into the
  feature's **living analysis**, `<prd_dir>/features/<feature>/analysis/`
  (ADR-0122 version front matter plus `feature` on every file of it) — always shared; a PRD
  folder that does not exist yet is confirmed first (`docs where --doc
  living:prd`, [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)). A run with no ticket MUST
  name or infer its feature: the one grouped ask proposes the PRD's feature
  slugs (`acs.py slug`), or a new slug when none fits.
- **Development** — a run with a ticket, or one `/acs:ship` drives (its
  first step), on a ticket or a prompt; `acs.py requirements refine` may set
  the phase explicitly: the analysis is
  written to `<development_dir>/<feature>/<ticket-id or run-id>/analysis/`
  — or keeps it in the run's step folder when the repo keeps run documents local ("Run documents: shared or kept local", [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)),
  and the survey MUST start from the feature's living analysis when one
  exists.

- Input: the run's requirements (`requirements.md` — the ticket, the prompt
  and the documents it was given), the PRD / requirements / architecture doc
  sets, the codebase, the clarification ledger and the previously published
  analysis, each read when present. Pre-hook check: the subject resolves.
  Brake: an **epic** ticket is refused (epics are designed and broken down
  with `/acs:breakdown-ticket`, never implemented).
- On a **bug** ticket MUST **reproduce first**: the analysis records the
  reproduction it ran (the steps, the command and what it showed against the
  ticket's `expected` and `actual`) or, when it could not reproduce the bug,
  says so as an open question — never a silent pass
  ([ADR-0138](../../architecture/adr/0138-breakdown-ticket-and-typed-ticket-authors.md)).
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
     answer is its own `clarify.py add` entry. Confirmed refined criteria,
     a confirmed `needs_design`, the features and the feature MUST be
     recorded through `acs.py requirements refine` — the run's
     `## Refined` requirements, and also a PATCH of the ticket when the run
     has one — so every later skill plans from the clarified requirements; a rejected proposal is recorded and not applied. At
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
     review, at most 3 rounds); the coordinator publishes it into the
        phase folder above and records the paths — it commits nothing
        ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)). A reviewer finding that is a
     new question for the user goes back through Stage 2.
- MUST write the analysis as a **folder**, `analysis/`, in its phase folder —
  never one long file, even when the change touches a single context
  ([ADR-0133](../../architecture/adr/0133-analysis-is-a-folder-by-bounded-context.md)):
  - `README.md`, the entry (never `index.md`), with front matter
    `{ticket | feature, ready_for_planning, needs_design_recommendation}`
    (plus ADR-0122's `status`, `version`, `tickets` on a Discovery analysis)
    and the headings, in order: `## Scope and summary`, `## Contexts`,
    `## Refined acceptance criteria`, `## Cross-cutting risks and decisions`,
    `## Questions and assumptions`, `## Verdict`. `## Contexts` is a table
    linking every context file of the folder, each with a one-line purpose;
    `## Questions and assumptions` lists every `C-n` with its answer or
    status and holds as assumptions only what the user did not answer;
    `## Refined acceptance criteria` (`AC-n`) states which criteria were
    confirmed into the requirements;
  - one file per **bounded context** the requirements touch, named in plain
    words in kebab-case (`order-checkout.md`), with front matter `context:
    <its file stem>` (plus `feature` and the version keys on Discovery) and
    the headings, in order: `## Impact map` (components, files and tests,
    each a repo-relative path cited `file:line`), `## Rules and edge cases`,
    `## Risks`, `## Open questions`, `## API notes`. A context file links to
    another rather than restating it. Contexts come from the impact
    analysts' code areas and the PRD features the requirements name.
- The impact reviewer MUST judge every file of the folder and the README's
  contexts table; `acs.py analysis record-draft` refuses a folder with no
  `README.md`, an `index.md`, a name that is not kebab-case `.md`, a
  missing or out-of-order heading, a table link that does not resolve or a
  context file the table does not list.
- MUST publish every reviewed file of the folder byte-for-byte and remove a
  context file the new analysis no longer has — only inside that
  `analysis/` folder.
- The published analysis is the reusable record: the feature's living
  analysis is read by `/create-architecture`, `/create-api-contract`,
  `/create-data-design`, `/create-flows`, `/create-tech-design` and by every later
  run on the feature; a Development run's is read by `/create-impl-plan`,
  `/create-test-docs` and `/code`, and the next run of this skill starts from
  it, each reading `README.md` first ("Reading an analysis: README first"
  above). A single `analysis.md` published before ADR-0133, and a legacy
  `docs/tickets/<ID>/analysis.md`, are still read when the phase folder has
  no `analysis/` folder; the workspace partition answers only when there is no
  checkout.
- The impact reviewer MUST check that every `## Questions for the user` item
  was answered in the ledger or carried as an open/assumed entry, and that
  every criterion the analysis marks confirmed matches the refined
  requirements.
- MUST NOT set any rigor itself. The stakes recommendation this step used to
  run over the impact paths went with the axis (ADR-0095); what replaces it is
  EVIDENCE, not a setting. When the impact map reaches a surface the repo
  treats as load-bearing — auth, payments, a migration or any stored shape, a
  public API, concurrency or ordering — the analysis MUST say so in that
  context file's `## Risks` (in README's `## Cross-cutting risks and
  decisions` when it spans contexts),
  naming the paths, because that is what `/create-impl-plan` carries into the
  plan and what the delivery-path judgement is then made from.
- A not-ready analysis MUST return `needs_input` rather than a completed run.
- MUST NOT record an API-surface verdict: `api_surface` left the front
  matter and the state with
  [ADR-0134](../../architecture/adr/0134-api-contract-is-a-design-document.md).
  Where the impact map shows an interface changing, the completion report's
  Next says so: "an interface changes — design it with
  `/acs:create-api-contract`". An analysis or a state file written before
  that still validates; the key is ignored.
- Subagents: `analyze-requirements-analyst` (requirements lane, synthesis and
  draft passes), `analyze-requirements-impact-analyst` (one code-impact lane per
  area — ADR-0114), `analyze-requirements-impact-reviewer` (analyse → impact
  review — ADR-0109). The loop is run by `acs.py analysis next` / `record-*` /
  `publish` (ADR-0114).
- State file: `analyze-requirements-state.json`; states `ready_for_planning`,
  `questions_open`.

## 2b. `/create-impl-plan`

Purpose: `/code`'s plan phase, carved out whole into its own skill, ending in
an approved `plan.md`.

- Input: the run's requirements, the analysis (its `README.md` first, then the context files the plan needs), `tech-design.md` (or a legacy `design.md`) and the approved API
  contract (`api-contract.md` through `acs.py artifacts show`, and the
  feature's `lld/<feature>/api/` files) when present; with none, the
  requirements alone. The contract is designed *before* the plan
  ([ADR-0134](../../architecture/adr/0134-api-contract-is-a-design-document.md)).
  Pre-hook check: the subject resolves. Brake: an epic is refused.
- When the repo keeps machine-readable contract files (OpenAPI, JSON Schema,
  proto, AsyncAPI) and the contract adds or changes an interface they
  describe, MUST plan the items that create or update them from the approved
  contract; `/code` implements them like any other item. The plan owes
  `test_cases` and `e2e` only — a plan written earlier that still carries
  `owes.api_contract` is accepted and that key ignored.
- MUST keep every mechanism the phase had inside `/code`, unchanged: the
  survey (the former planner charter, carried by the `planner` role), the
  spec fold, the executor file map, plan approval
  (`standard`/`complex` only, run by those legs) and the plan-revocation path
  (`plan-superseded-<k>.md` in the workspace).
- MUST write `plan.md` to the run's Development folder
  (`<development_dir>/<feature>/<ticket-id or run-id>/`, ADR-0128) — or keeps it in the run's step folder when the repo keeps run documents local ("Run documents: shared or kept local", [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)).
  It is always authored by the planner:
  the ADR-0074 fast path, on which the coordinator authored the plan itself
  with no subagent spawn, went with the lanes it forked on (ADR-0095). The
  plan-reviewer judges every draft, and on blocking findings the planner authors
  the remediation (ceiling 3
  review rounds — ADR-0074's 2026-09-14 amendment), so a fixable draft does
  not fail the run on its first verdict.
- MUST plan against the ticket as written when the analysis's `README.md` says
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

## 2c. `/create-test-docs`

Purpose: turn the run's acceptance criteria (plus the plan and the API
contract when they exist) into an explicit, traceable set of test cases,
before any test is written.

- Input: the requirements' acceptance criteria (`AC-n`, refined when
  `/analyze-requirements` refined them); `plan.md` when present; the API
  contract when present — `api-contract.md` through `acs.py artifacts show`
  and the feature's living `lld/<feature>/api/` files. Pre-hook check: the subject resolves.
- MUST write `test-cases.md` to the run's Development folder — or keeps it in the run's step folder when the repo keeps run documents local ("Run documents: shared or kept local", [ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)), with front
  matter `{ticket, cases}` (`ticket` only when there is one) and a
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
> first, write the code, leave it uncommitted in the working tree. `/code` implements the
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
- When an approved API contract exists (`api-contract.md` and the feature's
  `lld/<feature>/api/` files) and the repo keeps machine-readable contract
  files, the plan MUST carry the items that create or update those files
  from the contract, and `/code` implements them like any other item — the
  contract skill never writes them
  ([ADR-0134](../../architecture/adr/0134-api-contract-is-a-design-document.md)).
- When a design exists (the ticket's own or its parent epic's), the plan MUST
  **conform to it**, and `/review-code`'s lens C MUST check that conformance
  against `tech-design.md` and the architecture doc set.
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
  to `/breakdown-ticket <id>` (user-confirmed); the user MAY explicitly accept
  one large PR, recorded as a clarification. Implemented as a two-lever
  control after ADR 0066 (ADR 0069): `/create-ticket`'s upfront PR-size rubric
  fires before any decomposition exists; a non-blocking, plan-time oversize
  signal in the survey's charter item 2 fires once the decomposition itself is
  known, reusing the plan-simplicity gate's "surface, never block" contract to
  raise the same question through the clarification ledger. On a "split"
  answer the step ends `"failed"` with a `summary` naming the split, runs
  its mandatory Finish steps, and points at `/acs:breakdown-ticket <id>`, which
  reads the seams recorded in `steps/create-impl-plan/plan.md` (ADR-0138).
- MUST, for a **bug** ticket, make the first test of the first slice a
  failing **reproduction test** named for the bug, which proves the defect
  before any fix and passes after it; the plan reviewer checks it
  ([ADR-0138](../../architecture/adr/0138-breakdown-ticket-and-typed-ticket-authors.md)).
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
  `<run>/steps/code/plan-approval.json` — never a subagent's `acs.py write`, never
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
  of the change, not a follow-up. When it reconciles a factual claim in
  `prd.md` or `roadmap.md`, the implementer MUST record the change with
  `acs.py design bump` on that document — never by editing its front matter;
  a document without a block is left without one, and a `deprecated` one is
  not edited (the stale claim is flagged instead)
  ([ADR-0130](../../architecture/adr/0130-prd-versions-and-set-doc-status.md)).
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
  `/acs:create-tech-design`'s full step (for `needs_design: true` tickets)
  and `/acs:docs-sync`'s diff-grounded re-derivation.
- `/code` MUST NOT branch, stage or commit: implementers leave their files
  uncommitted and list them in their reports' `files_changed`; the run
  records them in `states.files`, and `/create-pr` commits them per plan
  slice ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)).
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
  outright with a `GateError` directing the user to `/acs:create-tech-design` (if
  the epic has no design yet), then `/acs:breakdown-ticket <id>`, then
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
- `/code` works in the working tree on whatever branch is checked out; the
  ticket branch (`<type>/<ticket-id>-<slug>`, so later skills and hooks can
  resolve context from it) is created by `/create-pr`. Concurrent tickets take
  a worktree each: one checkout has one working tree, so one changeset.

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
       else**), **C** contracts and architecture (`api-contract.md` and the
       feature's living `lld/<feature>/api/` files when they exist — no
       "nothing owed" branch since ADR-0134 — `tech-design.md`, architecture docs,
       the plan), **D** history and regression
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
  the ticket, left uncommitted and listed in `states.files`.
- Runs **in parallel with `/docs-sync`** in the default workflow — both need
  only `code` — as two members of one parallel group, each writing its own
  files into the same working tree, uncommitted
  ([workflow.md](workflow.md#parallel-work)).
- Subagents: `create-e2e-tests-test-writer`, `create-e2e-tests-suite-runner` (write → run — ADR-0109).
- State file: `create-e2e-tests-state.json`; states `suites_written`,
  `cases_covered`.

## 4. `/docs-sync`

Purpose: re-verify and complete the doc updates a ticket's changeset
requires — independently re-derived from the run's changeset
(`acs.py changes diff`), `/code`'s `result.json`, and the final code-verify
artifact, never from a hand-off summary alone.

- docs-sync NEVER creates a branch, commits or opens a PR: it writes its doc
  updates into the same working tree `/code` wrote, lists them in
  `states.files`, and `/create-pr` commits them as their own commit in the
  ticket's PR ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)).
- MUST gather, and never substitute a bare hand-off summary for: the live
  changeset (`acs.py changes diff`, untracked files included), the ticket JSON, `/code`'s
  `result.json` (`states.docs_updated`), `/code`'s implementer report(s)
  `problems` field, and the final code-verify artifact.
- MUST keep the run's features' low-level design current
  ([ADR-0137](../../architecture/adr/0137-docs-sync-keeps-the-feature-lld-current.md)).
  Its doc areas are `requirements`, `architecture` (the HLD and the flat
  `lld/flows/`), `lld`, `adr` and `general`, one doc-updater each; the `lld`
  area owns `<architecture_dir>/lld/<feature>/{api,data,flows,components}/**`
  for the run's features (`context.requirements.features`, else the ticket's
  `features`; none → no work) and never edits a run's record folder
  `lld/<feature>/<key>/`. In iteration 1, in the same message as the
  doc-updaters, one `docs-sync-gap-analyst` per feature (capped by
  `parallel.max_agents`) classifies every element of every living document —
  operation, entity, flow, component — `matches`, `unimplemented`,
  `undocumented` or `drifted`, with `file:line` evidence, the document's
  `status` and `version`, and a per-document `implemented-candidate` verdict
  when every element matches; the notes are joined into `iter-1/gaps.md`.
- MUST NOT silently rewrite an approved contract. A `proposed` (or
  unversioned) document is updated to match the code and bumped with
  `acs.py design bump`, and its unimplemented elements are left as planned. An
  undocumented or drifted element in an `approved` or `implemented` document
  is a question in the ONE grouped ask: update the document (bumped, so back
  to `proposed` for re-approval) or keep it — the code is wrong, a blocking
  finding for `/acs:code`; headless, it is recorded as a blocking finding and
  `needs_input`, never decided. A `deprecated` document is never touched.
- MUST move every `implemented-candidate` document `approved → implemented`
  after the review passes, in ONE `acs.py design status --set implemented
  --by acs --reason "<run-id>: the code matches" <doc>...` call, and list them
  in `states.implemented` (derived by the post-hook from each document's front
  matter) beside `states.files`. A document with any element still
  unimplemented stays `approved`.
- The drift reviewer judges seven dimensions in three slices; the seventh,
  `lld-currency` (in the `placement` slice with mechanics and
  requirements-routing), checks the feature LLD against the gap notes, that
  every edited document was bumped, that no approved or implemented document
  changed without a recorded answer, and that every move to `implemented` is
  backed by a candidate verdict whose evidence holds.
- Subagents: `docs-sync-doc-updater`, `docs-sync-gap-analyst`, `docs-sync-drift-reviewer` (update, with a gap survey beside it → drift review — ADR-0109, ADR-0137).
- State file: `docs-sync-state.json`, written by the post-hook
  ([workspace-and-state.md](workspace-and-state.md)).
- Declared position: in the default `ship.yaml`, `docs-sync` needs only
  `code` and runs in parallel with `create-e2e-tests`; `create-pr` needs
  `docs-sync` and `run-e2e-tests`. That position is **declared, not gated** —
  `/docs-sync`'s own pre-hook checks the partition and the lock and nothing
  else, so a hand-run `/docs-sync` proceeds (after one advisory line) even
  when `/code` has not completed ([hooks.md](hooks.md)).

## 5. `/create-pr`

Purpose: ship the implementation as a pull request — the one skill that
branches, commits and pushes ([ADR-0127](../../architecture/adr/0127-only-create-pr-commits.md)).

- MUST split the working tree's uncommitted changes into small reviewable
  commits with `acs.py pr plan-commits`: the ticket's documents, the design
  documents, per plan slice or file-map partition its tests then its code,
  `/docs-sync`'s updates, the e2e suites — built from what the steps recorded,
  intersected with the run's changeset. A run document kept local
  ([ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md))
  is never in the working tree, so it is in no group and never left out.
- MUST show that plan as a preview the user confirms (and may edit) before
  anything is committed, listing the changed files no step recorded (left out
  unless the user adds them) and the files already dirty when the run began
  (never included unless a step recorded them).
- MUST commit with `acs.py pr commit --plan <file>` — the run's branch
  (`<type>/<ticket-id>-<slug>` for a ticket) created when not already checked out, every
  group staged by pathspec, never `git add -A` — then push the branch and open
  the PR.
- MUST take a ticket id or a prompt, never require a ticket: with no
  argument it continues this checkout's current run (ticket- or
  prompt-subject); with a prompt and no current run it opens a prompt-subject
  run whose changeset is every uncommitted change against HEAD, grouped by
  layer — documents by doc set (the PRD, `hld/`, each `lld/<feature>/`, the
  ADRs, the run's documents), then tests, then code — placing each file by the
  paths other runs recorded in `states.files`. The `verifier_passed` brake
  applies only when the run has a code step; a commit subject names a ticket
  only when there is one, and a PR with no ticket is labelled `acs-exempt`.
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
- A PR opened from a prompt (`/create-pr "<prompt>"` — e.g. the PRD, the
  architecture, ADRs) names no ticket and carries `acs-exempt`, so it lands through
  `/merge-pr --pr <n>` like any other exempt PR
  ([Product-level delivery](#product-level-delivery-no-ticket)).
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
