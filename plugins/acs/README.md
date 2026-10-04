# acs — Autonomous Coding Skills

`acs` is a Claude Code plugin that turns a raw request into merged code
through a complete, agentic software-delivery workflow: product definition
(PRD), architecture, ticketing, design (when the change warrants it), TDD
implementation with an automatic review loop, a conditional post-code test
gate, doc sync, pull request, and merge. Each skill spawns only the
subagents its own work needs — a surveyor and an author and a reviewer for the
PRD, a planner and a plan reviewer for the plan, implementers for the code,
several instances of one role at once wherever the work splits into disjoint
slices —
the pipeline's order is declared in `workflows/ship.yaml` (each skill's own
hooks check only the safety brakes listed under *How gating works*, never a
predecessor's position or a missing upstream artifact, so a skill is runnable
on its own and works from the ticket, prompt or document it was given), the
human-facing ticket documents live in your repo under `docs/tickets/<id>/`,
and all durable run state lives in a
gitignored `.acs/state-machine` folder inside your repo — so runs
are resumable, tickets can ship in parallel across git worktrees, and the
coordinator never depends on conversation history between steps.

## Requirements

On the machine running Claude Code, inside the consumer repo:

| Tool | Required | Used for |
|------|----------|----------|
| `git` | Yes | Branches, worktrees, repo identity |
| `python3` 3.9+ | Yes | All hooks and helper CLIs (stdlib only — no pip installs) |
| `gh` (authenticated) | Yes | Pull requests; ticket sync when `tracker.provider` is `github` |

## Install

From the `gms-marketplace` marketplace (this repository):

```text
claude plugin marketplace add globalmindsolution/gms-marketplace
claude plugin install acs@gms-marketplace
```

Or through the UI: run `/plugin` inside a Claude Code session, add the
marketplace `globalmindsolution/gms-marketplace`, then install `acs` from it.

On **omp** (Oh My Pi) the same marketplace works — see
[Oh My Pi](../README.md#oh-my-pi) for install commands and two known
degradations (hooks ungated, `CLAUDE_PLUGIN_ROOT` must be exported).

## Quick start

No setup is required: acs runs in any repo on its defaults. Tickets are
`ACS-1`, `ACS-2`, …, and the workspace is the gitignored `.acs/state-machine`
folder in the main checkout — there is no path to pick. Run `/acs:setup` only
to change a convention or install the CI gates:

```text
cd acme-shop
/acs:setup
  → conventions?      keep the defaults  (branch task/ACS-12-slug, commit "ACS-12 …", PR "Add wishlist support")
  → CI?               conventions + tests gates   (optional; branch protection offered after)
```

Setup writes only what differs from a default, to `.acs/settings.json`. Every
other setting — ticket prefix, tracker, models, merge strategy, coverage
target — has a working default; change one by editing that file.

Onboard an existing product (brownfield) — baseline the PRD and the
architecture doc set, each delivered as a reviewable docs PR:

```text
/acs:create-prd            # reverse-engineers a baseline PRD from code + docs
                           # → delivery ticket ACS-1, docs PR
                           # if this is the first allocation for this
                           #   workspace partition, it refuses with exit 2
                           #   and proposes a start number from local
                           #   evidence — confirm or correct it with
                           #   --seed-next <n> (see Troubleshooting
                           #   below), then re-run; every later
                           #   allocation is normal
/acs:merge-pr ACS-1        # after you review the PR yourself

/acs:create-architecture   # reverse-engineers HLD (C4 1–3, data model,
                           #   deployment) + LLD key flows, all Mermaid
                           # → delivery ticket ACS-2, docs PR
/acs:merge-pr ACS-2
```

(Greenfield is the same, except both skills *elicit* instead of
reverse-engineer. Scaffolding the repo skeleton is then ordinary ticket work:
`/acs:create-ticket "Scaffold the repository per the architecture docs"`,
then `/acs:ship` on that ticket. The CI gates and the e2e workflow/runner
templates come from `/acs:setup`, and the principles and standards from
`/acs:create-docs`.)

Then ship features. `/acs:ship` takes a **ticket id**, so a new request starts
in the Design phase:

```text
/acs:create-ticket Add wishlist support so customers can save products for later
                           # → ACS-5, typed and traced to the PRD
/acs:create-design ACS-5   # only when the ticket carries needs_design: true
/acs:ship ACS-5            # drives the Build/Test/Ship steps to the PR
```

`/acs:ship` is a thin loop over `acs.py run next`: that command prints the
run's **derived** cursor — the first step in the resolved `workflows/ship.yaml`
(your `.acs/workflows/ship.yaml` when you ship one, else the plugin default)
that is not `completed`. Ship invokes that step, asks again, and repeats until
the list is done — always stopping before merge. Where the list declares a
**parallel group** (an entry that is itself a list — the default runs
`[create-e2e-tests, docs-sync]` as one), `run next` reports every unfinished
member in `due` and ship runs them side by side, spawning their subagents
together and asking you once for all of them. The cursor is never stored, so
it cannot disagree with the ledger it is read from. Print the file with
`acs.py workflow show` rather than assuming an order. After reviewing each PR yourself:

```text
/acs:merge-pr ACS-5        # readiness check → squash merge → delete branch →
                           #   ticket done (+ tracker sync) → partition archived
```

Every step is also invocable on its own (`/acs:create-ticket Fix flaky
checkout rounding`, then `/acs:analyze-requirements ACS-7`, `/acs:code ACS-7`, …).
A hand-run step is never refused for a predecessor's position in the workflow
or for a missing upstream artifact — its hook checks only the safety brakes
below, and the skill works from the ticket, prompt or document when an earlier
step's output is absent — so you can re-run one step, skip one you do not
need, or drive the whole thing yourself.
The ticket id argument is optional
when context is unambiguous: explicit argument → session context → branch
name.

## The 25 skills

The tables group the skills by phase — Design, Build, Test, Ship or
Utility. There is no registry file and no per-skill manifest: a skill is its
directory, and the surfaces that used to derive from a list (this table, the
set of nameable steps) read the skill directories instead, so adding a skill
is adding a directory. The order steps actually RUN in is declared
separately, in `workflows/ship.yaml`, which only keeps that order:
`acs.py workflow validate` checks that each step is a shipped skill and not a
leg, and that every loop goes back.

Not every skill is a command you run. Four **legs** — the delivery paths
behind `/acs:code`, listed in `acs_lib.skills.SKILL_LEGS` — keep their own
SKILL.md and stay Skill-invocable, but their only user-facing command is the
entry point they serve. That is an entry-point fold, not a collapse: nothing
about a leg's own run changed. The tables below show the entry points; the
legs get their own table under Design, and a leg's run reports under its entry
point. The
four doc-set legs `/acs:create-docs` used to fan out were a different case —
they differed only in a table row — so ADR-0094 folded them into it outright.

**Gate** says what each skill's pre-hook checks before letting it start: the
subject resolves, and the *safety brakes* — the lock; the epic refusal;
`/acs:code`'s plan approval; `/acs:create-pr`'s failed review;
`/acs:create-design`'s `needs_design`; `/acs:merge-pr`'s recorded PR
reference. No gate refuses a skill because an upstream artifact is missing
(the skill falls back to the run's subject) or for a *predecessor's position*
in the workflow — run a step out of the declared order and the pre-hook prints
a one-line advisory on stderr and the skill runs anyway. `/acs:merge-pr`'s brake does read whether the step that
recorded the PR reference completed — an artifact, not a position.

### Design — define the product and the ticket

| Skill | Gate | What it does |
|-------|----------------------|--------------|
| `/acs:create-prd` | Settings exist | Elicits (greenfield) or reverse-engineers (brownfield) the PRD doc set — the repo's own, else `docs/product/`; docs PR via its own delivery ticket. |
| `/acs:create-architecture` | Settings exist | Works from the PRD when there is one; without one, from the run's subject (a document in its arguments, else your focus notes plus the codebase), confirming goals, NFRs and constraints through the clarification ledger. Writes the high-level design only — `hld/` overview, tech stack and cross-cutting conventions plus the HLD types enabled at `/acs:setup` (C4 levels 1–3, conceptual data model, API landscape, deployment, project structure; opt-in data-flow and capability maps) — in the repo's architecture set, else `docs/architecture/`, all Mermaid; never `lld/`; docs PR. |
| `/acs:create-docs` | Settings exist; the skill itself stops at Start without the architecture doc set | Bootstraps or maintains the four product doc sets — `quality` (test strategy, coverage policy), `operations` (release process, runbooks, observability, incident response, test scheduling), `principles` (engineering principles + rationale), `standards` (coding standards, conventions, review checklist) — from the plugin's templates, tailored to the PRD and the architecture set. Takes `all`, a comma-separated list of sets, or a delivery-ticket id to resume one; runs the eligible sets in capped parallel (at most 2 at a time, a limit the skill sets for itself — `ship.yaml` carries no `max_parallel`), each as its own docs-only PR on its own delivery ticket. One author and one reviewer serve every set (the set rides in the task constraints); `standards` reads the `principles` set when present and never blocks on its absence. |
| `/acs:create-ticket` | Settings exist | Turns a prompt (or an imported remote key) into a typed ticket (epic/story/task) with PRD tracing, `needs_design` flag, optional GitHub Projects sync. Also `--fan-out` to mint a designed epic's children. |
| `/acs:create-design` | Ticket resolves; ticket has `needs_design: true` | Weighs options with you and writes `design.md` (decision, architecture, NFRs, risks) for the ticket; an epic's children inherit it. |

#### Internal legs — not commands you run

The legs are one table in the plugin's code, `acs_lib.skills.SKILL_LEGS`;
nothing in a leg's own directory marks it. Each keeps its SKILL.md and its
entry point invokes it as a genuine Skill-tool call; each says in its
description that it is an internal leg, so use the entry point instead.

| Leg | Entry point | Gate | What it does |
|-----|-------------|----------------------|--------------|
| `code-trivial` | `/acs:code` | Subject resolves; not an epic | The `trivial` delivery path: one implementer, the plan's own test strategy as the test contract, no plan approval. |
| `code-small` | `/acs:code` | Subject resolves; not an epic | The `small` delivery path: one implementer (rarely two), `test-cases.md` as the test contract, no plan approval. |
| `code-standard` | `/acs:code` | Subject resolves; not an epic; the plan's approval matches the plan on disk | The `standard` delivery path: one implementer per disjoint file-map partition, `test-cases.md` as the test contract, plan approval enforced. |
| `code-complex` | `/acs:code` | Subject resolves; not an epic; the plan's approval matches the plan on disk | The `complex` delivery path: one implementer per partition **plus an integration implementer** over the seams between them, plan approval enforced. |

**The four `code` legs are delivery paths (ADR-0095), not modes a user picks.**
`/acs:create-impl-plan` judges the path ONCE, from the plan's own scope, and
records it in the plan's `## Contract` block; `/acs:code` reads it with
`acs.py plan path` and dispatches to the recorded leg. They own no agents
and no hook scripts: each starts
`acs.py step start --step code`, passes `code`'s gate, spawns
`acs:code-implementer` and finishes through `post-code.py`,
so everything they write on disk is `code`'s. The protocol they share lives in
`skills/code/references/`; each leg's SKILL.md carries only what makes its path
different.

### Build — analyze, plan, specify, implement

| Skill | Gate | What it does |
|-------|----------------------|--------------|
| `/acs:analyze-requirements` | Ticket resolves; not an epic | Reads the ticket, the product docs and the codebase and writes `analysis.md`: problem restated, impact map, recorded questions, assumptions, risks, refined acceptance criteria, and the `api_surface` verdict the pipeline branches on. |
| `/acs:create-api-contract` | Ticket resolves; not an epic; nothing owed (an evidenced no-op) when the plan declares no API surface | Writes `api-contract.md` — every endpoint/command/message the plan adds or changes, shapes, error codes, compatibility notes, examples — each traced to an AC and a plan item, plus the machine-readable contract files where the repo keeps them, else under `docs/api/`. |
| `/acs:create-impl-plan` | Ticket resolves; not an epic | The plan phase carved out of `/acs:code`: a planner surveys and drafts (the former planner charter), the spec fold, the executor file map, and plan approval, and a plan reviewer judges the draft, ending in an approved `plan.md`. Reads `analysis.md` and `design.md` when present, else works from the ticket. |
| `/acs:create-test-docs` | Ticket resolves | Writes `test-cases.md` — `TC-n` cases typed unit/integration/e2e, each traced to an acceptance criterion, with preconditions, steps, expected result and target suite. Every AC must be covered by at least one case. |
| `/acs:code` | Subject resolves; not an epic | Dispatches to the delivery-path leg the plan recorded (ADR-0095). TDD implementation on the run's branch, writing tests from `test-cases.md` when present. **Targeted tests only** — it has no verifier and never runs the full suite. |
| `/acs:review-code` | Subject resolves; a changeset exists | The changeset review: five read-only lenses in parallel, one fresh-context adjudicator per candidate finding prompted to refute it, then a final gate running build, lint, the full unit suite and coverage. Writes `verdict.json`; on blocking findings `/acs:code` reads it and fixes them. |
| `/acs:docs-sync` | Ticket resolves (partition + free lock) | Independently re-derives doc impact from the diff, `/code`'s `result.json`, and `/acs:review-code`'s verdict; commits doc updates as additional commits on the same ticket branch — not a separate PR. |

### Test — end-to-end coverage

| Skill | Gate | What it does |
|-------|----------------------|--------------|
| `/acs:create-e2e-tests` | Ticket resolves; not an epic (the skill itself asks for a suite when none is configured, and owes nothing when there is no e2e case) | Writes the ticket's e2e suites at the repo's configured e2e location, covering the e2e-typed rows of `test-cases.md`, committed on the ticket branch. |
| `/acs:run-e2e-tests` | Nothing owed (an evidenced no-op) when the plan declares no e2e impact | Runs this product's configured test suites (all, or a `--suite`-selected subset), captures pass/fail results to an auditable run artifact, and on failure triages/drives a closed regression-ticket loop. It is a step of `ship.yaml` and a standing command, on one protocol. |

### Ship — review and land

| Skill | Gate | What it does |
|-------|----------------------|--------------|
| `/acs:create-pr` | Brake: refuses a run whose `/acs:review-code` step left `verifier_passed != true` | Pushes the ticket branch and opens the PR (configured title/description formats, `ACS` label) against the default branch. A ticket with no recorded code run is allowed through. |
| `/acs:merge-pr` | Brake: a completed run recorded a PR reference | Readiness check (CI, approvals, conflicts, protections), merge per `merge_strategy`, delete branch, mark ticket done, archive the partition. Also `/acs:merge-pr --pr <n>` (or `#n` / PR URL) to land a legitimate non-ticket **`acs-exempt`** PR — same readiness + cleanup, no ticket/partition/tracker. |
| `/acs:release` | — (unhooked) | Assembles/verifies the CHANGELOG section for a release version from the merged-ticket archive, bumps version-location files, dates the section, and opens an exempt `release/*` PR for a mandatory human merge. Fails fast if no `release` block is configured. |

### Utility — setup and orchestration

| Skill | Gate | What it does |
|-------|----------------------|--------------|
| `/acs:setup` | — (optional; no skill needs it first) | Sets the ticket prefix and installs the CI gates: the optional ticket-link check (every PR names its ticket), tests and e2e; can scaffold the `models` block and write `.claude/launch.json`, the Desktop app's preview-server config. Writes `.acs/settings.json` (never a value equal to its default); every other setting is edited by hand. Re-runs update in place. |
| `/acs:update` | — (utility, user-invoked only) | Upgrade assistant: installed-vs-latest version check, CHANGELOG delta with breaking-change callouts, marketplace refresh, post-update migration checks (settings, a leftover acs status line). Reloading stays your action. |
| `/acs:handoff` | — (utility) | Flushes in-flight work and decisions to the run, marks the in-flight step `interrupted` with a `stop_reason`, releases the lock, prints the command to continue in a fresh session. |
| `/acs:ship` | — (each step keeps its own gate) | **Takes a ticket id.** Thin loop over `acs.py run next` — the run's derived cursor, the first step in `ship.yaml` order that is not completed. Invokes that step (every member at once when the cursor sits in a parallel group), then asks again, until the list is done. Never merges. |

## How gating works

- **Order lives in `workflows/ship.yaml`; the hooks keep the brakes.**
  A `PreToolUse` hook on the `Skill` tool (`dispatch.py pre`) runs the named
  skill's gate in-process. Exit 2 blocks the skill before any of its
  instructions run; stderr names the brake that fired. No gate refuses a skill
  because an upstream artifact is missing — the skill falls back to the run's
  subject — or for a *predecessor's position* in the workflow, so every skill
  is runnable on its own. The one refusal that names a
  predecessor's completion is `/acs:merge-pr`'s subject brake, which asks
  whether the step that recorded the PR reference completed — an artifact, not
  a position.
- **Out-of-order runs get one advisory line, not a refusal.** When a hooked
  skill runs before a step that precedes it in the resolved workflow has
  completed, the pre-hook prints exactly one line on stderr —
  `acs: review-code normally follows code in ship.yaml; the cursor for SHOP-12
  is code` — and exits 0. A member of a parallel group that is due alongside
  another member is not out of order and gets no line. Set `workflow.advisories: false` to silence it.
- **The brakes that survive are facts, not order.** `/acs:code` refuses a
  standard or complex run whose plan approval is missing or is for a different
  revision of the plan on disk; `/acs:create-pr` refuses a run whose recorded
  `/acs:review-code` step did not pass; `/acs:create-design`
  refuses a ticket that is not flagged `needs_design`; and `/acs:merge-pr`
  refuses without a PR reference recorded by a completed run. An epic id is
  refused by the steps that would work it as one ticket, and every hooked
  skill refuses while another session holds the ticket's `.lock`.
- **Post-hooks close the loop without trusting the model.** Each skill's
  coordinator must call `post-<skill>.py --result-file …` as its mandatory
  final step; that is the only thing that flips the run to `completed`. Skill
  start has already recorded the step `in_progress`, and the cursor `acs.py run
  next` derives is the first step that is not `completed` — so a skipped
  post-hook leaves the step un-completed and the pipeline re-offers it, never
  skips past it.
- **A `SessionEnd` safety net** (`dispatch.py session-end`) finalizes any
  run this checkout left `in_progress` as `interrupted` and releases its
  lock, so abnormal endings still write state.

## Where things live

Durable state is split in two: the **documents a human reads or reviews** are
committed in your repo, and the **run ledger** stays in the gitignored
workspace.

```text
<repo>/docs/tickets/<ticket-id>/        # fixed location, not a setting
  ticket.md      # front matter = the ticket fields; body = description, ACs, clarifications
  design.md  analysis.md  api-contract.md  plan.md  test-cases.md

<workspace>/<repo-id>/                  # repo-id from git remote: owner-name
  tickets-index.json  runs-index.json  counters.json
  sessions/<checkout-id>/               # one directory per worktree
    pointer.json                        # the run and step this checkout is on
  archive/<run-id>/                     # moved here by post-merge-pr
  runs/<run-id>/                        # the run id is derived from the subject
    run.json                            # THE RUN MACHINE
    subject/                            # ticket.json | prompt.md | the document
    requirements.md  clarifications.json
    lock.json  lock-events.jsonl  agents/  handoff-context.md
    steps/<skill>/
      state.json                        # THE STEP MACHINE
      result.json                       # the post-hook's input
      plan.md  api-contract.md  test-cases.md  …   # the CURRENT artifacts
      iter-<n>/                         # the audit trail: one dir per iteration
```

Two machines, not one. `run.json` records the run — its workflow, its subject,
its position in the loop; `steps/<skill>/state.json` records that step's own
invocations. Keeping them apart is what lets a skill the workflow never names
(`/acs:create-design`, say) hold step state without taking a position in any
run.

`ticket.md` carries no `status` field — status is DERIVED from the ledger
(`open` → `in_progress` → `in_review` → `done`), so the committed document and
the run state can never disagree. An existing repo moves its artifacts across
once with `acs.py artifacts migrate` (add `--dry-run` to preview; it is
idempotent and leaves a `ticket.json.moved` pointer behind).
`acs.py artifacts show --ticket <id>` prints where each of a ticket's
artifacts actually resolved.

Subagents may not write inside the ticket docs tree — it is a control input the
file-map guard denies, like the guard's own records.

Inspect progress anytime: `tickets-index.json` for status across tickets,
`runs-index.json` for every run, `acs.py run show` for where a run stands,
and `acs.py run next` for what runs next.

## Configuration

No settings file is required. `/acs:setup` writes the conventions; everything
else is edited by hand and validated against
[schemas/settings.schema.json](schemas/settings.schema.json). Resolved per key
as `settings.local.json` → project `settings.json` → `~/.acs/settings.json`,
over the built-in defaults. The most-used keys:

| Key | Default | Purpose |
|-----|---------|---------|
| `ticket_prefix` | `"ACS"` | Ticket id prefix (`ACS` → `ACS-123`); optional — set your own by hand (`SHOP` → `SHOP-123`) |
| `tests` | `{ "coverage": 90 }` | `{coverage?, unit?, e2e?, <name>?}`: `coverage` is the `/acs:code` TDD coverage target (hard fail if missed) and the CI tests-gate floor; `unit` is the CI tests-gate suite (`{command, setup?}`); `e2e` and every other key are named suites (`{command, setup?, teardown?}`) |
| `merge_strategy` | `"squash"` | `/acs:merge-pr`: `squash` \| `merge` \| `rebase` |
| `models` | inherit | Model + reasoning effort per subagent, `models.<skill>.<role> = {model, effort}` (a model alias or id, an effort `low`…`max`, or `inherit`). Written in full by `acs.py settings scaffold --write`; `acs step start` turns each entry that sets a value into a `.claude/agents/acs-<skill>-<role>.md` copy and spawns that. An absent skill, role or field inherits the parent session |
| `tracker` | `{ "provider": "local" }` | Ticket backend: `local` or `github` (Projects v2); `gh` is the only transport |

No key locates a document: acs finds the repo's documents through `CLAUDE.md`
and the repo itself, creates a missing one at the `docs/` conventions
(`docs/product/`, `docs/architecture/`, `docs/architecture/adr/`, …), and keeps ticket
documents at the fixed `docs/tickets/<ID>/` (ADR-0102). No key locates the
workspace either: it is always `.acs/state-machine` in the main checkout.

Full reference: [docs/requirements/functional/configuration.md](../../docs/requirements/functional/configuration.md)
(all keys, placeholder vocabulary, description templates, tracker mapping)
and the machine-readable
[schemas/settings.schema.json](schemas/settings.schema.json).

## Migrating old settings

The settings shape changed (`test_coverage_percent`, `suites` and the top-level `e2e` moved under `tests`; Jira support was removed). `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" settings migrate` shows what it would rewrite (a dry run); add `--write` to rewrite every existing settings file to the new shape. Until a settings file is migrated every acs skill refuses to start, with a message naming the offending keys and this command. `/acs:update` runs it as its post-update settings step.

## Migrating an existing external workspace

If this repo's state still lives in an external workspace outside the repo
(from before the in-repo workspace shipped), acs no longer reads it — the
workspace is always `.acs/state-machine` in the main checkout (ADR-0102) — so
move it across once:

```text
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/migrate_workspace.py" \
  --from <old-workspace-root> --to <repo>/.acs/state-machine \
  --repo-root <repo-root>
```

The migrator preflights (refuses if a `.lock` is held or a run is
`in_progress`), copies the repo's partition tree, verifies the copy, then
removes the old tree; it is idempotent, so it is safe to re-run if
interrupted. Add `--dry-run` to preview without writing. The old
`workspace_path` key left in `.acs/settings.local.json` is ignored and can be
deleted.

## Troubleshooting

- **"no plan for this run; working from the ticket" (skill runs anyway).**
  A skill whose usual input is missing does not refuse: it works from the
  ticket, prompt or document and says so in its report. Run the producing
  step first (here `/acs:create-impl-plan SHOP-123`) when you want its output
  used.
- **"acs: docs-sync normally follows review-code in ship.yaml …" (skill runs
  anyway).** That is the out-of-order ADVISORY, not a refusal — one stderr line,
  exit 0. It means the step you invoked is ahead of the run's cursor in the
  resolved workflow; ignore it when that is deliberate, or run the named step first.
  `workflow.advisories: false` silences it.
- **"/acs:review-code ran for this run and did not pass".** A brake, not an
  order check: `/acs:create-pr` refuses while the run's review has blocking
  findings. Fix them with `/acs:code SHOP-123` and re-run
  `/acs:review-code SHOP-123` until it passes.
- **"blocked — … has never allocated a ticket id" (first ticket in a new
  repo or a fresh clone).** The first allocation for a `(repo_id, prefix)`
  partition refuses with exit 2 instead of restarting the sequence at 1. The
  message proposes a start number from local evidence (a *floor*, not the
  truth — your tracker may hold higher ids) — confirm or correct it by
  re-running the same command with `--seed-next <n>` added (e.g.
  `/acs:create-ticket`'s Start, or `new-ticket.py --seed-next <n>`
  directly). An already-populated workspace (every existing repo) is
  already treated as reconciled and never sees this.
- **"another session holds the lock."** Each ticket partition has a `.lock`
  owned by one session. If the other session is live (e.g. a parallel
  worktree), finish or hand off there. If it crashed, ending that session
  normally releases the lock via the `SessionEnd` hook; after a hard kill
  the lock is stale — verify the owning process is gone, then delete
  `<workspace>/<repo>/<ticket-id>/.lock` and re-run the skill.
- **Crash or interruption mid-skill.** The run entry stays `in_progress`
  (or is finalized `interrupted`), so the workflow walk simply offers that step
  again. Re-run the same skill (or `/acs:ship <ticket-id>`) — the
  coordinator sees the unfinished run and *reconciles* recorded state
  against reality (e.g. re-runs tests for specs marked implemented) before
  continuing. The per-iteration artifacts under `steps/<skill>/iter-<n>/` mean
  at most the in-flight iteration is lost.
- **Corrupt or missing state files.** Treated as *not completed* — and since
  the cursor is derived as the first step that is not `completed`, `acs.py run
  next` re-offers it rather than letting a half-recorded step count as done.
  Re-run that skill for the ticket to regenerate its state.
- **Long session running out of context.** Run `/acs:handoff`: it flushes
  in-flight work and decisions to the run, marks the in-flight step
  `interrupted` with a `stop_reason` of `context_pressure`, releases the lock,
  and prints the exact command (e.g. `/acs:code SHOP-123`) to continue in a
  fresh session.

## For contributors

The binding implementation contract — skill lifecycle, helper CLIs (`acs.py`,
`new-ticket.py`, `handoff.py`, `plan-approval.py`), result-document shape,
canonical `states` keys, the JSON Schemas, and subagent conventions — lives in
[docs/INTERNALS.md](docs/INTERNALS.md). The
business requirements live in the repo's
[docs/](../../docs/README.md) folder.
