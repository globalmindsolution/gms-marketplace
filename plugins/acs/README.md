# acs — Autonomous Coding Skills

`acs` is a Claude Code plugin that turns a raw request into merged code
through a complete, agentic software-delivery workflow: product definition
(PRD), architecture, ticketing, design (when the change warrants it), TDD
implementation with an automatic review loop, a conditional post-code test
gate, doc sync, pull request, and merge. Every workflow skill runs a plan → execute → verify
reflection cycle with dedicated subagents, the pipeline's order is declared in
`workflows/ship.yaml` (each skill's own hooks check only the inputs it reads
and a couple of safety brakes, so every skill is runnable on its own), the
human-facing ticket documents live in your repo under `docs/tickets/<id>/`,
and all durable run state lives in a
gitignored `.acs/state-machine` folder inside your repo by default (an
explicit `workspace_path` override can still point it elsewhere) — so runs
are resumable, tickets can ship in parallel across git worktrees, and the
coordinator never depends on conversation history between steps.

## Requirements

On the machine running Claude Code, inside the consumer repo:

| Tool | Required | Used for |
|------|----------|----------|
| `git` | Yes | Branches, worktrees, repo identity |
| `python3` 3.9+ | Yes | All hooks and helper CLIs (stdlib only — no pip installs) |
| `gh` (authenticated) | Yes | Pull requests; ticket sync when `tracker.provider` is `github` |
| `acli` (authenticated) | Only with `tracker.provider: "jira"` | Jira ticket sync |
| `xmllint` | Optional | Full XSD validation of agent messages (structural fallback otherwise) |

## Install

From the `gms-marketplace` marketplace (this repository):

```text
claude plugin marketplace add globalmindsolution/gms-marketplace
claude plugin install acs@gms-marketplace
```

Or through the UI: run `/plugin` inside a Claude Code session, add the
marketplace `globalmindsolution/gms-marketplace`, then install `acs` from it.

## Quick start

One-time setup in any repo (the workspace defaults to a gitignored in-repo
folder — no path to pick unless you want one):

```text
cd acme-shop
/acs:setup
  → scope?            project            (.acs/settings.json + gitignored .acs/settings.local.json)
  → workspace_path?   <default>          (.acs/state-machine in this checkout; set an override only if you want state elsewhere)
  → ticket_prefix?    SHOP               (suggested from the repo name)
  → coverage 90, merge_strategy squash, tracker local  (defaults, editable)
```

Onboard an existing product (brownfield) — baseline the PRD and the
architecture doc set, each delivered as a reviewable docs PR:

```text
/acs:create-prd            # reverse-engineers a baseline PRD from code + docs
                           # → delivery ticket SHOP-1, docs PR
                           # if this is the first allocation for this
                           #   workspace partition since /acs:setup, it
                           #   refuses with exit 2 and proposes a start
                           #   number from local evidence — confirm or
                           #   correct it with --seed-next <n> (see
                           #   Troubleshooting below), then re-run; every
                           #   later allocation is normal
/acs:merge-pr SHOP-1       # after you review the PR yourself

/acs:create-architecture   # reverse-engineers HLD (C4 1–3, data model,
                           #   deployment) + LLD key flows, all Mermaid
                           # → delivery ticket SHOP-2, docs PR
/acs:merge-pr SHOP-2
```

(Greenfield is the same, except both skills *elicit* instead of
reverse-engineer, and one extra `/acs:project` run scaffolds the repo
skeleton — build, test harness, coverage tooling, lint, CI, a green vertical
slice. `/acs:project` finds no packaging or build file on disk, says so, and
dispatches to its `bootstrap` leg; run in an existing repo it picks
`standardize` instead and audits rather than scaffolds.)

Then ship features. `/acs:ship` takes a **ticket id**, so a new request starts
in the Design phase:

```text
/acs:create-ticket Add wishlist support so customers can save products for later
                           # → SHOP-5, typed and traced to the PRD
/acs:create-design SHOP-5  # only when the ticket carries needs_design: true
/acs:ship SHOP-5           # drives the Build/Test/Ship steps to the PR
```

`/acs:ship` is a thin loop over `acs.py workflow next`: it reads the resolved
`workflows/ship.yaml` (your `.acs/workflows/ship.yaml` when you ship one, else
the plugin default), invokes whatever step is ready, fans independent steps out
in parallel across worktrees, and repeats until `stop_after` — always stopping
before merge. Print the file with `acs.py workflow show` rather than assuming an
order. After reviewing each PR yourself:

```text
/acs:merge-pr SHOP-5       # readiness check → squash merge → delete branch →
                           #   ticket done (+ tracker sync) → partition archived
```

Every step is also invocable on its own (`/acs:create-ticket Fix flaky
checkout rounding`, then `/acs:analyze-ticket SHOP-7`, `/acs:code SHOP-7`, …).
A hand-run step is never refused for being out of order — its hook checks only
that the inputs it reads exist — so you can re-run one step, skip one you do
not need, or drive the whole thing yourself. The ticket id argument is optional
when context is unambiguous: explicit argument → session context → branch
name.

## The 32 skills

Skills are grouped into five phases by `workflows/phases.yaml` — the registry
every other surface derives from (this table, the ship-workflow schema's
allowed-skill list, `/acs:metrics` grouping). Within a phase the rows follow
the registry's own order; the order steps actually RUN in is declared
separately, in `workflows/ship.yaml`.

Not every skill is a command you run. The registry's `internal` map names six
**legs** — four doc-bootstrap skills behind `/acs:create-docs`, the two
project-scaffold skills behind `/acs:project` — that keep their own SKILL.md,
agent trio, `pre-`/`post-` hooks and gate, and stay Skill-invocable, but whose
only user-facing command is the entry point they serve. That is an entry-point
fold, not a collapse: nothing about a leg's own run changed. The tables below
show the entry points; the legs get their own table under Design, where all
six of them sit, and a leg's run reports under its entry point's phase
(`phase_of("create-quality")` is `design`, resolved through `create-docs`).

**Gate** says what each skill's pre-hook checks before letting it start. Since
v0.5.0 a gate checks only *inputs* (the artifacts and configuration the skill
reads) and *safety brakes* (the partition lock; a failed verifier). No gate
refuses a skill for running before another one — run out of the declared order,
the pre-hook prints a one-line advisory on stderr and the skill runs anyway.

### Design — define the product and the ticket

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:create-prd` | Settings exist | Elicits (greenfield) or reverse-engineers (brownfield) the PRD doc set at `prd_path`; docs PR via its own delivery ticket. |
| `/acs:create-requirements` | Settings exist | Bootstraps or amends the requirements/ doc set (functional + non-functional, one file per feature/item) at `requirements_path` — brownfield reverse-engineers it code-cited, greenfield elicits it interactively, amend augments only absent/ungrounded areas; docs PR via its own delivery ticket. |
| `/acs:create-architecture` | PRD doc set exists | HLD (C4 levels 1–3, data model, deployment, tech stack) + LLD (sequence-diagram flows, contracts) at `architecture_path`, all Mermaid; docs PR. |
| `/acs:create-docs` | — (unhooked umbrella; each leg keeps its own gate) | The only user-facing command for the four product doc sets — `quality`, `operations`, `principles`, `standards`. Takes `all` or a comma-separated list (the `create-<set>` spelling resolves too; `--for` is accepted for one more release and says so once). Filters the request through the declared eligibility predicate, then fans the eligible legs out in capped parallel — at most 2 at a time (the ship workflow's `max_parallel`) — each leg delivering its own docs-only PR on its own delivery ticket. |
| `/acs:project` | — (unhooked umbrella; each leg keeps its own gate) | The only user-facing command for repository structure and tooling. Decides its own mode from declared on-disk evidence (`acs_lib.PROJECT_MODE_SENTINEL` — ten packaging/build/tooling files): no evidence at all ⇒ `bootstrap`, any evidence ⇒ `standardize`. States the mode and the evidence it rests on, then dispatches to that leg as a real Skill-tool call. |
| `/acs:create-ticket` | Settings exist | Turns a prompt (or an imported remote key) into a typed ticket (epic/story/task) with PRD tracing, `needs_design` flag, optional Jira/GitHub Projects sync. Also `--fan-out` to mint a designed epic's children. |
| `/acs:create-design` | Ticket resolves; ticket has `needs_design: true` | Weighs options with you and writes `design.md` (decision, architecture, NFRs, risks) for the ticket; an epic's children inherit it. |

#### Internal legs — not commands you run

These six are the `internal` map of `workflows/phases.yaml`. Each keeps its
SKILL.md, its planner/executor/verifier trio, its `pre-`/`post-` hook scripts,
its registered gate and its sentinel, and its entry point invokes it as a
genuine Skill-tool call so all of that fires exactly as it would standalone.
What changed is only who invokes them: each carries
`disable-model-invocation: true`, so use the entry point instead. A leg's own
`/acs:<leg>` command survives for one purpose — resuming a leg that failed, was
interrupted or was handed off, which its entry point never does on its behalf.
Each leg's own `argument-hint` says what that resume takes: the four doc legs
take the delivery-ticket id, and `create-project` takes no argument at all (it
finds its own unfinished scaffold ticket in `tickets-index.json`).

| Leg | Entry point | Gate (input / brake) | What it does |
|-----|-------------|----------------------|--------------|
| `create-quality` | `/acs:create-docs` | Architecture doc set exists | Bootstraps or maintains the quality/ doc set (test strategy, coverage policy) at `quality_path`, reading the PRD's non-functional requirements and the architecture set; docs PR via its own delivery ticket. |
| `create-operations` | `/acs:create-docs` | Architecture doc set exists | Bootstraps or maintains the operations/ doc set (release process, runbooks, observability, incident response, test-scheduling recipe) at `operations_path`, reading the PRD's non-functional requirements and the architecture set; docs PR via its own delivery ticket. |
| `create-principles` | `/acs:create-docs` | Architecture doc set exists | Bootstraps or maintains the principles/ doc set (engineering principles + rationale) at `principles_path`, reading the PRD and the architecture set; docs PR via its own delivery ticket. |
| `create-standards` | `/acs:create-docs` | Architecture doc set exists | Bootstraps or maintains the standards/ doc set (coding standards, naming/layout/formatting conventions, review checklist) at `standards_path`, reading the PRD, the architecture set, and the principles set when present; docs PR via its own delivery ticket. Declares a soft dependency on `create-principles`, which is why the two never share a fan-out batch. |
| `create-project` | `/acs:project` | Architecture doc set exists | Greenfield-only: scaffolds layout, build, test framework + coverage tooling, lint, CI, and a minimal green vertical slice; bootstrap PR. The `bootstrap` mode's leg. |
| `standardize-project` | `/acs:project` | Architecture doc set exists | Audits an EXISTING repo against `principles_path`/`standards_path`, `hld/project-structure.md`, and acs-readiness tooling (coverage/CI/pre-commit/e2e), then additively scaffolds only the missing docs/config/tooling — never moves, renames, deletes, or rewrites existing source; one reviewed PR. The `standardize` mode's leg. |

### Build — analyze, plan, specify, implement

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:analyze-ticket` | Ticket resolves; not an epic | Reads the ticket, the product docs and the codebase and writes `analysis.md`: problem restated, impact map, recorded questions, assumptions, risks, refined acceptance criteria, and the `api_surface` verdict the pipeline branches on. |
| `/acs:create-api-contract` | `plan.md` exists **and** `analysis.md` declares `api_surface: true` | Writes `api-contract.md` — every endpoint/command/message the plan adds or changes, shapes, error codes, compatibility notes, examples — each traced to an AC and a plan item, plus the machine-readable contract files under `contracts_path` when the repo keeps them. |
| `/acs:create-impl-plan` | Ticket resolves; not an epic | The plan phase carved out of `/acs:code`: the planner agent, the spec fold, the executor file map, and plan approval, ending in an approved `plan.md`. Reads `analysis.md` and `design.md` when present. |
| `/acs:create-test-docs` | Ticket resolves | Writes `test-cases.md` — `TC-n` cases typed unit/integration/e2e, each traced to an acceptance criterion, with preconditions, steps, expected result and target suite. Every AC must be covered by at least one case. |
| `/acs:code` | Ticket resolves; not an epic; `plan.md` exists | TDD implementation on a ticket branch against the coverage target, writing tests from `test-cases.md` when present; reconciles factual product-doc claims; verifier review loop (max 3 iterations). |
| `/acs:docs-sync` | Ticket resolves (partition + free lock) | Independently re-derives doc impact from the diff, `/code`'s `result.json`, and the final code-verify artifact; commits doc updates as additional commits on the same ticket branch — not a separate PR. |

### Test — end-to-end coverage

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:create-e2e-tests` | An e2e suite is configured **and** `test-cases.md` lists ≥ 1 e2e case | Writes the ticket's e2e suites at the repo's configured e2e location, covering the e2e-typed rows of `test-cases.md`, committed on the ticket branch. |
| `/acs:run-e2e-tests` | — (unhooked) | Runs this product's configured test suites (all, or a `--suite`-selected subset), captures pass/fail results to an auditable workspace artifact, and on failure triages/drives a closed regression-ticket loop; `--for-ticket` mode runs as one step inside `/acs:ship`'s walk. |
| `/acs:test` | — (unhooked alias) | Deprecated alias kept for one release: forwards to `/acs:run-e2e-tests`. `workflows/phases.yaml` lists it under `aliases`, never in a phase. |

### Ship — review and land

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:create-pr` | Brake: refuses a ticket whose recorded `/acs:code` run left `verifier_passed != true` | Pushes the ticket branch and opens the PR (configured title/description formats, `ACS` label) against the default branch. A ticket with no recorded code run is allowed through. |
| `/acs:merge-pr` | Brake: a completed run recorded a PR reference | Readiness check (CI, approvals, conflicts, protections), merge per `merge_strategy`, delete branch, mark ticket done, archive the partition. Also `/acs:merge-pr --pr <n>` (or `#n` / PR URL) to land a legitimate non-ticket **`acs-exempt`** PR — same readiness + cleanup, no ticket/partition/tracker. |
| `/acs:release` | — (unhooked) | Assembles/verifies the CHANGELOG section for a release version from the merged-ticket archive, bumps version-location files, dates the section, and opens an exempt `release/*` PR for a mandatory human merge. Fails fast if no `release` block is configured. |

### Utility — setup, orchestration, reporting

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:setup` | — (bootstrap) | Generates `.acs/settings.json` (user or project scope): workspace path, ticket prefix, coverage target, formats, tracker, artifact paths, advisories. Opt-in (default-on) writes a pipeline-default `CLAUDE.md` managed block so sessions ship via `/acs:ship`, not raw `gh pr create`. Re-runs update in place. |
| `/acs:install-hooks` | — (utility, user-invoked only) | Installs this clone's local convention hooks (`commit-msg` + `pre-push`) that enforce the configured `formats.*` before push — the `pre-commit install` equivalent for acs. Per-clone; each teammate runs it once. |
| `/acs:update` | — (utility, user-invoked only) | Upgrade assistant: installed-vs-latest version check, CHANGELOG delta with breaking-change callouts, marketplace refresh, post-update migration checks (settings, status-line paths). Reloading stays your action. |
| `/acs:handoff` | — (utility) | Flushes in-flight work and decisions to the ticket partition, marks the run `handed_off`, releases the lock, prints the command to continue in a fresh session. |
| `/acs:metrics` | — (utility) | Read-only in-session dashboard: renders the PM delivery view: delivery summary, throughput, pipeline funnel, ISSUES, PROGRESS, DEADLINE, coverage, review iterations, lead/cycle time — from workspace state. Writes nothing. |
| `/acs:usage` | — (utility) | Read-only in-session usage dashboard: renders the usage view — usage summary, cost and time per ticket by step, the four per-ticket/per-PR averages, token burn by role — from workspace state. Writes nothing. |
| `/acs:ship` | — (each step keeps its own gate) | **Takes a ticket id.** Thin loop over `acs.py workflow next`: reads the resolved `ship.yaml`, invokes the ready step (or fans several ready steps out in parallel, one worktree per leg), and repeats until `stop_after`. Never merges. |

## How gating works

- **Order lives in `workflows/ship.yaml`; the hooks keep inputs and brakes.**
  A `PreToolUse` hook on the `Skill` tool (`dispatch.py pre`) runs the named
  skill's gate in-process. Exit 2 blocks the skill before any of its
  instructions run; stderr names the missing input and the skill that produces
  it (e.g. "no plan.md found for SHOP-12 … run /acs:create-impl-plan SHOP-12
  first"). What a gate never does any more is refuse because a *predecessor*
  has not completed — every skill is runnable on its own.
- **Out-of-order runs get one advisory line, not a refusal.** When a hooked
  skill's `needs` in the resolved workflow are not satisfied for the ticket,
  the pre-hook prints exactly one line on stderr —
  `acs: docs-sync normally follows code in ship.yaml; code has not completed
  for SHOP-12` — and exits 0. Set `workflow.advisories: false` to silence it.
- **Two brakes survive, because they are facts, not order.** `/acs:create-pr`
  refuses a ticket whose recorded `/acs:code` run left the verifier failing,
  and `/acs:merge-pr` refuses without a PR reference recorded by a completed
  run. Every hooked skill also refuses while another session holds the
  ticket's `.lock`.
- **Post-hooks close the loop without trusting the model.** Each skill's
  coordinator must call `post-<skill>.py --result-file …` as its mandatory
  final step; that is the only thing that flips the run to `completed`. Skill
  start has already recorded an `in_progress` run entry, and the ledger is what
  `acs.py workflow next` walks — so a skipped post-hook leaves the step
  un-satisfied and the pipeline re-offers it, never skips past it.
- **A `SessionEnd` safety net** (`dispatch.py session-end`) finalizes any
  run this checkout left `in_progress` as `interrupted` and releases its
  lock, so abnormal endings still write state.

## Where things live

Durable state is split in two: the **documents a human reads or reviews** are
committed in your repo, and the **run ledger** stays in the gitignored
workspace.

```text
<repo>/docs/tickets/<ticket-id>/        # artifacts.tickets_path (default)
  ticket.md      # front matter = the ticket fields; body = description, ACs, clarifications
  design.md  analysis.md  api-contract.md  plan.md  test-cases.md

<workspace>/<repo-id>/                  # repo-id from git remote: owner-name
  tickets-index.json  counters.json  metrics.json
  sessions/<checkout-id>.json           # per-worktree current-ticket pointer
  archive/<ticket-id>/                  # moved here by post-merge-pr
  <ticket-id>/
    .lock  pipeline-state.json  clarifications.json
    ticket.json.moved                   # pointer left where ticket.json was
    specs/NN-slug.md
    phases/<skill>/iter-<n>-<phase>.xml  phases/<skill>/result.json
    <skill>-state.json ...
```

`ticket.md` carries no `status` field — status is DERIVED from the ledger
(`open` → `in_progress` → `in_review` → `done`), so the committed document and
the run state can never disagree. An existing repo moves its artifacts across
once with `acs.py artifacts migrate` (add `--dry-run` to preview; it is
idempotent and leaves a `ticket.json.moved` pointer behind). Set
`artifacts.tickets_path: null` to opt out entirely and keep every artifact in
the workspace partition exactly as before. `acs.py artifacts show --ticket <id>`
prints where each of a ticket's artifacts actually resolved.

Executors may not write inside the ticket docs tree — it is a control input the
file-map guard denies, like the guard's own records.

Inspect progress and spend anytime: `tickets-index.json` for status across
tickets, `metrics.json` for per-repo totals, a ticket's
`pipeline-state.json` for where it stands in the pipeline, and
`acs.py workflow next --ticket <id>` for what runs next.

## Configuration

Generated by `/acs:setup`; resolved per key as `settings.local.json` →
project `settings.json` → `~/.acs/settings.json`. The most-used keys:

| Key | Default | Purpose |
|-----|---------|---------|
| `workspace_path` | unset (derives `.acs/state-machine` in the main checkout) | State folder; an explicit override lives in gitignored `settings.local.json` |
| `ticket_prefix` | — (required at setup time) | Per-repo ticket id prefix (`SHOP` → `SHOP-123`) |
| `test_coverage_percent` | `90` | `/acs:code` TDD coverage target (hard fail if missed) |
| `merge_strategy` | `"squash"` | `/acs:merge-pr`: `squash` \| `merge` \| `rebase` |
| `prd_path` | `"docs/product"` | PRD doc set location in the repo |
| `architecture_path` | `"docs/architecture"` | HLD/LLD doc set location in the repo |
| `adr_path` | unset | When set, `/acs:docs-sync` commits accepted decision records here |
| `models` | inherit | Per-role model + reasoning effort (`planner`/`executor`/`verifier`, per-skill overrides) |
| `tracker` | `{ "provider": "local" }` | Ticket backend: `local`, `github` (Projects v2), or `jira` |
| `formats` | built-ins | Branch/commit/PR/ticket formats (`branch_name` must embed `{ticket_id}`) |

Full reference: [docs/requirements/functional/configuration.md](../../docs/requirements/functional/configuration.md)
(all keys, placeholder vocabulary, description templates, tracker mapping)
and the machine-readable
[schemas/settings.schema.json](schemas/settings.schema.json).

## Migrating an existing external workspace

If this repo has an existing `workspace_path` pointing outside the repo (set
before the in-repo default shipped), `/acs:setup` detects it and offers
to migrate on your next re-run. To migrate by hand instead:

```text
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/migrate_workspace.py" \
  --from <old-workspace-root> --to <repo>/.acs/state-machine \
  --repo-root <repo-root>
```

The migrator preflights (refuses if a `.lock` is held or a run is
`in_progress`), copies the repo's partition tree, verifies the copy, then
removes the old tree; it is idempotent, so it is safe to re-run if
interrupted. Add `--dry-run` to preview without writing. Once it succeeds,
remove the `workspace_path` key from `.acs/settings.local.json` so future
runs resolve the new in-repo default instead of the old override.

## Troubleshooting

- **"no plan.md found for SHOP-123 …" (skill refuses to run).** A pre-hook
  exited 2 because an INPUT it reads is missing. The stderr message names the
  file, where it looked, and the skill that produces it — run that one for the
  same ticket (here `/acs:create-impl-plan SHOP-123`). A "run /setup first"
  message means no `settings.json` could be resolved: run `/acs:setup`.
- **"acs: docs-sync normally follows code in ship.yaml …" (skill runs
  anyway).** That is the out-of-order ADVISORY, not a refusal — one stderr line,
  exit 0. It means the step you invoked is ahead of its `needs` in the resolved
  workflow; ignore it when that is deliberate, or run the named step first.
  `workflow.advisories: false` silences it.
- **"/code ran for SHOP-123 but its verifier did not pass".** A brake, not an
  order check: the ticket HAS a recorded `/acs:code` run whose review loop never
  reached zero findings. Re-run `/acs:code SHOP-123` until it does.
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
  continuing. Phase artifacts under `phases/<skill>/` mean at most the
  in-flight phase is lost.
- **Corrupt or missing state files.** Treated as *not completed* — the step
  stays un-satisfied, so `acs.py workflow next` re-offers it rather than
  letting a half-recorded step count as done. Re-run that skill for the ticket
  to regenerate its state.
- **Long session running out of context.** Run `/acs:handoff`: it flushes
  in-flight work and decisions to the ticket partition, releases the lock,
  and prints the exact command (e.g. `/acs:code SHOP-123`) to continue in a
  fresh session.

## For contributors

The binding implementation contract — skill lifecycle, helper CLIs
(`skill-start.py`, `new-ticket.py`, `handoff.py`, `validate_xml.py`),
result-document shape, canonical `states` keys, XML messaging rules, and
subagent conventions — lives in [docs/INTERNALS.md](docs/INTERNALS.md). The
business requirements live in the repo's
[docs/](../../docs/README.md) folder.
