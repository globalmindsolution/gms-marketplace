# acs — Autonomous Coding Skills

`acs` is a Claude Code plugin that turns a raw request into merged code
through a complete, agentic software-delivery workflow: product definition
(PRD), architecture, ticketing, design (when the change warrants it), TDD
implementation with an automatic review loop, a conditional post-code test
gate, doc sync, pull request, and merge. Every workflow skill runs a plan → execute → verify
reflection cycle with dedicated subagents, the pipeline's order is declared in
`workflows/ship.yaml` (each skill's own hooks check the inputs it reads and the
safety brakes listed under *How gating works*, never a predecessor's position,
so a skill is runnable on its own), the
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

`/acs:ship` is a thin loop over `acs.py run next`: that command prints the
run's **derived** cursor — the first step in the resolved `workflows/ship.yaml`
(your `.acs/workflows/ship.yaml` when you ship one, else the plugin default)
that is not `completed`. Ship invokes that step, asks again, and repeats until
the list is done — always stopping before merge. The cursor is never stored, so
it cannot disagree with the ledger it is read from. Print the file with
`acs.py workflow show` rather than assuming an order. After reviewing each PR yourself:

```text
/acs:merge-pr SHOP-5       # readiness check → squash merge → delete branch →
                           #   ticket done (+ tracker sync) → partition archived
```

Every step is also invocable on its own (`/acs:create-ticket Fix flaky
checkout rounding`, then `/acs:analyze-requirements SHOP-7`, `/acs:code SHOP-7`, …).
A hand-run step is never refused for a predecessor's position in the workflow —
its hook checks the inputs it reads and the safety brakes below — so you can
re-run one step, skip one you do not need, or drive the whole thing yourself.
The ticket id argument is optional
when context is unambiguous: explicit argument → session context → branch
name.

## The 32 skills

Each skill declares its own phase — Design, Build, Test, Ship or Utility — in
`skills/<name>/acs.yaml`, beside the artifacts it reads and writes. There is no
registry file: the surfaces that used to derive from one (this table,
`/acs:metrics` grouping, the set of nameable steps) read the skill directories
instead, so adding a skill is adding a directory. The order steps actually RUN
in is declared separately, in `workflows/ship.yaml`, and `acs.py workflow
validate` checks that order against each skill's declared reads and writes.

Not every skill is a command you run. Six **legs** — the project-scaffold
skills behind `/acs:project` and the four delivery paths behind `/acs:code` —
carry `disable-model-invocation: true` and keep their
own SKILL.md, agent trio, `pre-`/`post-` hooks and gate, and stay
Skill-invocable, but whose only user-facing command is the entry point they
serve. That is an entry-point fold, not a collapse: nothing about a leg's own
run changed. The tables below show the entry points; the legs get their own
table under Design, and a leg's run reports under its entry point's phase
(`phase_of("create-project")` is `design`, resolved through `project`). The
four doc-set legs `/acs:create-docs` used to fan out were a different case —
they differed only in a table row — so ADR-0094 folded them into it outright.

**Gate** says what each skill's pre-hook checks before letting it start. Since
v0.5.0 a gate checks *inputs* (the artifacts and configuration the skill
reads) and *safety brakes*: the lock; the epic refusal; `/acs:code`'s plan
approval; `/acs:create-pr`'s failed verifier; `/acs:create-design`'s
`needs_design`; `/acs:merge-pr`'s recorded PR reference. No gate refuses a
skill for a *predecessor's position* in the workflow — run a step out of the
declared order and the pre-hook prints a one-line advisory on stderr and the
skill runs anyway. `/acs:merge-pr`'s brake does read whether the step that
recorded the PR reference completed — an artifact, not a position.

### Design — define the product and the ticket

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:create-prd` | Settings exist | Elicits (greenfield) or reverse-engineers (brownfield) the PRD doc set at `prd_path`; docs PR via its own delivery ticket. |
| `/acs:create-requirements` | Settings exist | Bootstraps or amends the requirements/ doc set (functional + non-functional, one file per feature/item) at `requirements_path` — brownfield reverse-engineers it code-cited, greenfield elicits it interactively, amend augments only absent/ungrounded areas; docs PR via its own delivery ticket. |
| `/acs:create-architecture` | PRD doc set exists | HLD (C4 levels 1–3, data model, deployment, tech stack) + LLD (sequence-diagram flows, contracts) at `architecture_path`, all Mermaid; docs PR. |
| `/acs:create-docs` | Architecture doc set exists | Bootstraps or maintains the four product doc sets — `quality` (test strategy, coverage policy), `operations` (release process, runbooks, observability, incident response, test scheduling), `principles` (engineering principles + rationale), `standards` (coding standards, conventions, review checklist) — from the plugin's templates, tailored to the PRD and the architecture set. Takes `all`, a comma-separated list of sets, or a delivery-ticket id to resume one; runs the eligible sets in capped parallel (at most 2 at a time, a limit the skill sets for itself — `ship.yaml` carries no `max_parallel`), each as its own docs-only PR on its own delivery ticket. One executor and one verifier serve every set (the set rides in the task constraints); `standards` reads the `principles` set when present and never blocks on its absence. |
| `/acs:project` | — (unhooked umbrella; each leg keeps its own gate) | The only user-facing command for repository structure and tooling. Decides its own mode from declared on-disk evidence (`acs_lib.PROJECT_MODE_SENTINEL` — ten packaging/build/tooling files): no evidence at all ⇒ `bootstrap`, any evidence ⇒ `standardize`. States the mode and the evidence it rests on, then dispatches to that leg as a real Skill-tool call. |
| `/acs:create-ticket` | Settings exist | Turns a prompt (or an imported remote key) into a typed ticket (epic/story/task) with PRD tracing, `needs_design` flag, optional Jira/GitHub Projects sync. Also `--fan-out` to mint a designed epic's children. |
| `/acs:create-design` | Ticket resolves; ticket has `needs_design: true` | Weighs options with you and writes `design.md` (decision, architecture, NFRs, risks) for the ticket; an epic's children inherit it. |

#### Internal legs — not commands you run

A leg is marked by `disable-model-invocation: true` in its own SKILL.md front
matter — there is no registry listing them. Each project leg keeps its
SKILL.md, its executor/verifier pair, its `pre-`/`post-` hook scripts,
its registered gate and its sentinel, and its entry point invokes it as a
genuine Skill-tool call so all of that fires exactly as it would standalone.
What changed is only who invokes them: each says in its description that it
is an internal leg, so use the entry point instead. A leg's own `/acs:<leg>`
command survives for one purpose — resuming a leg that failed, was interrupted
or was handed off, which its entry point never does on its behalf.
`create-project` takes no argument at all (it finds its own unfinished
scaffold ticket in `tickets-index.json`).

| Leg | Entry point | Gate (input / brake) | What it does |
|-----|-------------|----------------------|--------------|
| `create-project` | `/acs:project` | Architecture doc set exists | Greenfield-only: scaffolds layout, build, test framework + coverage tooling, lint, CI, and a minimal green vertical slice; bootstrap PR. The `bootstrap` mode's leg. |
| `standardize-project` | `/acs:project` | Architecture doc set exists | Audits an EXISTING repo against `principles_path`/`standards_path`, `hld/project-structure.md`, and acs-readiness tooling (coverage/CI/pre-commit/e2e), then additively scaffolds only the missing docs/config/tooling — never moves, renames, deletes, or rewrites existing source; one reviewed PR. The `standardize` mode's leg. |
| `code-trivial` | `/acs:code` | Subject resolves; not an epic; a plan exists | The `trivial` delivery path: one executor, the plan's own test strategy as the test contract, no plan approval. |
| `code-small` | `/acs:code` | Subject resolves; not an epic; a plan exists | The `small` delivery path: one executor (rarely two), `test-cases.md` as the test contract, no plan approval. |
| `code-standard` | `/acs:code` | Subject resolves; not an epic; an approved plan exists | The `standard` delivery path: one executor per disjoint file-map partition, `test-cases.md` as the test contract, plan approval enforced. |
| `code-complex` | `/acs:code` | Subject resolves; not an epic; an approved plan exists | The `complex` delivery path: one executor per partition **plus an integration executor** over the seams between them, plan approval enforced. |

**The four `code` legs are delivery paths (ADR-0095), not modes a user picks.**
`/acs:create-impl-plan` judges the path ONCE, from the plan's own scope, and
records it in the plan's `## Contract` block; `/acs:code` reads it with
`acs.py plan path` and dispatches to the recorded leg. They differ from the
project legs in owning no agents and no hook scripts: each starts
`acs.py step start --step code`, passes `code`'s gate, spawns
`acs:code-executor` and finishes through `post-code.py`,
so everything they write on disk is `code`'s. The protocol they share lives in
`skills/code/references/`; each leg's SKILL.md carries only what makes its path
different.

### Build — analyze, plan, specify, implement

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:analyze-requirements` | Ticket resolves; not an epic | Reads the ticket, the product docs and the codebase and writes `analysis.md`: problem restated, impact map, recorded questions, assumptions, risks, refined acceptance criteria, and the `api_surface` verdict the pipeline branches on. |
| `/acs:create-api-contract` | `plan.md` exists **and** `analysis.md` declares `api_surface: true` | Writes `api-contract.md` — every endpoint/command/message the plan adds or changes, shapes, error codes, compatibility notes, examples — each traced to an AC and a plan item, plus the machine-readable contract files under `contracts_path` when the repo keeps them. |
| `/acs:create-impl-plan` | Ticket resolves; not an epic | The plan phase carved out of `/acs:code`: the executor's survey (the former planner charter), the spec fold, the executor file map, and plan approval, ending in an approved `plan.md`. Reads `analysis.md` and `design.md` when present. |
| `/acs:create-test-docs` | Ticket resolves | Writes `test-cases.md` — `TC-n` cases typed unit/integration/e2e, each traced to an acceptance criterion, with preconditions, steps, expected result and target suite. Every AC must be covered by at least one case. |
| `/acs:code` | Subject resolves; not an epic; a plan exists | Dispatches to the delivery-path leg the plan recorded (ADR-0095). TDD implementation on the run's branch, writing tests from `test-cases.md` when present. **Targeted tests only** — it has no verifier and never runs the full suite. |
| `/acs:review-code` | Subject resolves; a changeset exists | The changeset review: five read-only lenses in parallel, one fresh-context adjudicator per candidate finding prompted to refute it, then a final gate running build, lint, the full unit suite and coverage. Writes `verdict.json`; on blocking findings `/acs:code` reads it and fixes them. |
| `/acs:docs-sync` | Ticket resolves (partition + free lock) | Independently re-derives doc impact from the diff, `/code`'s `result.json`, and `/acs:review-code`'s verdict; commits doc updates as additional commits on the same ticket branch — not a separate PR. |

### Test — end-to-end coverage

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:create-e2e-tests` | An e2e suite is configured **and** `test-cases.md` lists ≥ 1 e2e case | Writes the ticket's e2e suites at the repo's configured e2e location, covering the e2e-typed rows of `test-cases.md`, committed on the ticket branch. |
| `/acs:run-e2e-tests` | A suite is configured and there are e2e cases to run | Runs this product's configured test suites (all, or a `--suite`-selected subset), captures pass/fail results to an auditable run artifact, and on failure triages/drives a closed regression-ticket loop. It is a step of `ship.yaml` and a standing command, on one protocol. |

### Ship — review and land

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:create-pr` | Brake: refuses a run whose `/acs:review-code` step left `verifier_passed != true` | Pushes the ticket branch and opens the PR (configured title/description formats, `ACS` label) against the default branch. A ticket with no recorded code run is allowed through. |
| `/acs:merge-pr` | Brake: a completed run recorded a PR reference | Readiness check (CI, approvals, conflicts, protections), merge per `merge_strategy`, delete branch, mark ticket done, archive the partition. Also `/acs:merge-pr --pr <n>` (or `#n` / PR URL) to land a legitimate non-ticket **`acs-exempt`** PR — same readiness + cleanup, no ticket/partition/tracker. |
| `/acs:release` | — (unhooked) | Assembles/verifies the CHANGELOG section for a release version from the merged-ticket archive, bumps version-location files, dates the section, and opens an exempt `release/*` PR for a mandatory human merge. Fails fast if no `release` block is configured. |

### Utility — setup, orchestration, reporting

| Skill | Gate (input / brake) | What it does |
|-------|----------------------|--------------|
| `/acs:setup` | — (bootstrap) | Generates `.acs/settings.json` (user or project scope): workspace path, ticket prefix, coverage target, formats, tracker, artifact paths, advisories. Opt-in (default-on) writes a pipeline-default `CLAUDE.md` managed block so sessions ship via `/acs:ship`, not raw `gh pr create`. Re-runs update in place. |
| `/acs:install-hooks` | — (utility, user-invoked only) | Installs this clone's local convention hooks (`commit-msg` + `pre-push`) that enforce the configured `formats.*` before push — the `pre-commit install` equivalent for acs. Per-clone; each teammate runs it once. |
| `/acs:update` | — (utility, user-invoked only) | Upgrade assistant: installed-vs-latest version check, CHANGELOG delta with breaking-change callouts, marketplace refresh, post-update migration checks (settings, status-line paths). Reloading stays your action. |
| `/acs:handoff` | — (utility) | Flushes in-flight work and decisions to the run, marks the in-flight step `interrupted` with a `stop_reason`, releases the lock, prints the command to continue in a fresh session. |
| `/acs:metrics` | — (utility) | Read-only in-session dashboard: renders the PM delivery view: delivery summary, throughput, pipeline funnel, ISSUES, PROGRESS, DEADLINE, coverage, review iterations, lead/cycle time — from workspace state. Writes nothing. |
| `/acs:usage` | — (utility) | Read-only in-session usage dashboard: renders the usage view — usage summary, cost and time per ticket by step, the four per-ticket/per-PR averages, token burn by role — from workspace state. Writes nothing. |
| `/acs:ship` | — (each step keeps its own gate) | **Takes a ticket id.** Thin loop over `acs.py run next` — the run's derived cursor, the first step in `ship.yaml` order that is not completed. Invokes that step, then asks again, until the list is done. Never merges. |

## How gating works

- **Order lives in `workflows/ship.yaml`; the hooks keep inputs and brakes.**
  A `PreToolUse` hook on the `Skill` tool (`dispatch.py pre`) runs the named
  skill's gate in-process. Exit 2 blocks the skill before any of its
  instructions run; stderr names the missing input and the skill that produces
  it (e.g. "no plan.md found for SHOP-12 … run /acs:create-impl-plan SHOP-12
  first"). No gate refuses a skill for a *predecessor's position* in the
  workflow — every skill is runnable on its own. The one refusal that names a
  predecessor's completion is `/acs:merge-pr`'s subject brake, which asks
  whether the step that recorded the PR reference completed — an artifact, not
  a position.
- **Out-of-order runs get one advisory line, not a refusal.** When a hooked
  skill runs before a step that precedes it in the resolved workflow has
  completed, the pre-hook prints exactly one line on stderr —
  `acs: docs-sync normally follows code in ship.yaml; code has not completed
  for SHOP-12` — and exits 0. Set `workflow.advisories: false` to silence it.
- **The brakes that survive are facts, not order.** `/acs:code` refuses a
  standard or complex run whose plan approval is missing or is for a different
  revision of the plan on disk; `/acs:create-pr` refuses a run whose recorded
  `/acs:review-code` step left the verifier failing; `/acs:create-design`
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
<repo>/docs/tickets/<ticket-id>/        # artifacts.tickets_path (default)
  ticket.md      # front matter = the ticket fields; body = description, ACs, clarifications
  design.md  analysis.md  api-contract.md  plan.md  test-cases.md

<workspace>/<repo-id>/                  # repo-id from git remote: owner-name
  tickets-index.json  runs-index.json  counters.json  metrics.json
  sessions/<checkout-id>/               # one directory per worktree
    pointer.json                        # the run and step this checkout is on
    session.json  cost.jsonl  runtime.json
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
idempotent and leaves a `ticket.json.moved` pointer behind). Set
`artifacts.tickets_path: null` to opt out entirely and keep every artifact in
the workspace partition exactly as before. `acs.py artifacts show --ticket <id>`
prints where each of a ticket's artifacts actually resolved.

Executors may not write inside the ticket docs tree — it is a control input the
file-map guard denies, like the guard's own records.

Inspect progress and spend anytime: `tickets-index.json` for status across
tickets, `runs-index.json` for every run, `metrics.json` for per-repo totals,
`acs.py run show` for where a run stands, and `acs.py run next` for what runs
next.

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
| `models` | inherit | Per-role model + reasoning effort (`executor`/`verifier`, per-skill overrides; a `planner` entry is still accepted but no skill spawns one — ADR-0092) |
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
