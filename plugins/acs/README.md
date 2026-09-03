# acs — Autonomous Coding Skills

`acs` is a Claude Code plugin that turns a raw request into merged code
through a complete, agentic software-delivery workflow: product definition
(PRD), architecture, ticketing, design (when the change warrants it),
implementation specs, TDD implementation with an automatic review loop, pull
request, and merge. Every workflow skill runs a plan → execute → verify
reflection cycle with dedicated subagents, pre/post hooks gate each step on
the recorded state of its predecessor, and all durable state lives in a
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
                           # in a brand-new repo, this first allocation
                           #   refuses with exit 2 — confirm once with
                           #   --seed-next 1 (see Troubleshooting below),
                           #   then re-run; every later allocation is normal
/acs:merge-pr SHOP-1       # after you review the PR yourself

/acs:create-architecture   # reverse-engineers HLD (C4 1–3, data model,
                           #   deployment) + LLD key flows, all Mermaid
                           # → delivery ticket SHOP-2, docs PR
/acs:merge-pr SHOP-2
```

(Greenfield is the same, except both skills *elicit* instead of
reverse-engineer, and one extra `/acs:create-project` run scaffolds the repo
skeleton — build, test harness, coverage tooling, lint, CI, a green vertical
slice.)

Then ship features:

```text
/acs:ship Add wishlist support so customers can save products for later
```

`/acs:ship` runs `/acs:create-ticket` → `/acs:create-design` (when the
ticket needs design) → `/acs:code` → `/acs:docs-sync` → `/acs:create-pr`,
asking clarifying questions along the way — and always stops before merge.
After reviewing each PR yourself:

```text
/acs:merge-pr SHOP-5       # readiness check → squash merge → delete branch →
                           #   ticket done (+ tracker sync) → partition archived
```

Every step is also invocable on its own (`/acs:create-ticket Fix flaky
checkout rounding`, then `/acs:code SHOP-7`, …) —
the hooks enforce the order either way. The ticket id argument is optional
when context is unambiguous: explicit argument → session context → branch
name.

## The 25 skills

| Skill | Gated by | What it does |
|-------|----------|--------------|
| `/acs:setup` | — (bootstrap) | Generates `.acs/settings.json` (user or project scope): workspace path, ticket prefix, coverage target, formats, tracker. Opt-in (default-on) writes a pipeline-default `CLAUDE.md` managed block so sessions ship via `/acs:ship`, not raw `gh pr create`. Re-runs update in place. |
| `/acs:ship` | Each step's own gate | Umbrella: drives create-ticket → design → code → docs-sync → create-pr end to end, resumable from the first incomplete step. Never merges. |
| `/acs:handoff` | — (utility) | Flushes in-flight work and decisions to the ticket partition, marks the run `handed_off`, releases the lock, prints the command to continue in a fresh session. |
| `/acs:update` | — (utility, user-invoked only) | Upgrade assistant: installed-vs-latest version check, CHANGELOG delta with breaking-change callouts, marketplace refresh, post-update migration checks (settings, status-line paths). Reloading stays your action. |
| `/acs:install-hooks` | — (utility, user-invoked only) | Installs this clone's local convention hooks (`commit-msg` + `pre-push`) that enforce the configured `formats.*` before push — the `pre-commit install` equivalent for acs. Per-clone; each teammate runs it once. |
| `/acs:metrics` | — (utility) | Read-only in-session dashboard: renders the PM delivery view: delivery summary, throughput, pipeline funnel, ISSUES, PROGRESS, DEADLINE, coverage, review iterations, lead/cycle time — from workspace state. Writes nothing. |
| `/acs:usage` | — (utility) | Read-only in-session usage dashboard: renders the usage view — usage summary, cost and time per ticket by step, the four per-ticket/per-PR averages, token burn by role — from workspace state. Writes nothing. |
| `/acs:test` | — (utility) | Runs this product's configured test suites (all, or a `--suite`-selected subset), captures pass/fail results to an auditable workspace artifact, and on failure triages/drives a closed regression-ticket loop; `--for-ticket` mode runs as one step inside `/acs:ship`'s pipeline walk. |
| `/acs:release` | — (utility) | Assembles/verifies the CHANGELOG section for a release version from the merged-ticket archive, bumps version-location files, dates the section, and opens an exempt `release/*` PR for a mandatory human merge. Fails fast if no `release` block is configured. |
| `/acs:create-docs` | — (utility) | Cross-skill doc-bootstrap fan-out: detects independent doc-bootstrap skills (currently `create-quality` and `create-operations`) whose upstream prerequisites are satisfied, and runs them in parallel instead of sequentially — each leg keeps its own hooks, reflection cycle, and gating, and delivers as its own docs-only PR on its own delivery ticket. |
| `/acs:create-prd` | `/acs:setup` done | Product-level: elicits (greenfield) or reverse-engineers (brownfield) the PRD doc set at `prd_path`; docs PR via its own delivery ticket. |
| `/acs:create-architecture` | PRD doc set exists | Product-level: HLD (C4 levels 1–3, data model, deployment, tech stack) + LLD (sequence-diagram flows, contracts) at `architecture_path`, all Mermaid; docs PR. |
| `/acs:create-project` | Architecture doc set exists | Product-level, greenfield-only: scaffolds layout, build, test framework + coverage tooling, lint, CI, and a minimal green vertical slice; bootstrap PR. |
| `/acs:create-quality` | Architecture doc set exists | Product-level: bootstraps or maintains the quality/ doc set (test strategy, coverage policy) at `quality_path`, reading the PRD's non-functional requirements and the architecture set; docs PR via its own delivery ticket. |
| `/acs:create-operations` | Architecture doc set exists | Product-level: bootstraps or maintains the operations/ doc set (release process, runbooks, observability, incident response, test-scheduling recipe) at `operations_path`, reading the PRD's non-functional requirements and the architecture set; docs PR via its own delivery ticket. |
| `/acs:create-principles` | Architecture doc set exists | Product-level: bootstraps or maintains the principles/ doc set (engineering principles + rationale) at `principles_path`, reading the PRD and the architecture set; docs PR via its own delivery ticket. |
| `/acs:create-standards` | Architecture doc set exists | Product-level: bootstraps or maintains the standards/ doc set (coding standards, naming/layout/formatting conventions, review checklist) at `standards_path`, reading the PRD, the architecture set, and the principles set when present; docs PR via its own delivery ticket. |
| `/acs:create-requirements` | `/acs:setup` done | Product-level: bootstraps or amends the requirements/ doc set (functional + non-functional, one file per feature/item) at `requirements_path` — brownfield reverse-engineers it code-cited, greenfield elicits it interactively, amend augments only absent/ungrounded areas; docs PR via its own delivery ticket. |
| `/acs:create-ticket` | Settings exist | Turns a prompt (or an imported remote key) into a typed ticket (epic/story/task) with PRD tracing, `needs_design` flag, optional Jira/GitHub Projects sync. |
| `/acs:create-design` | `/acs:create-ticket` completed; ticket has `needs_design: true` | Weighs options with you and writes `design.md` (decision, architecture, NFRs, risks) in the ticket partition; epics' children inherit it. |
| `/acs:code` | `/acs:create-ticket` completed | TDD implementation on a ticket branch against the coverage target; reconciles factual product-doc claims; verifier review loop (max 3 iterations). |
| `/acs:docs-sync` | `/acs:code` completed (**and** `/acs:test`, when it ran) | Independently re-derives doc impact from the diff, `/code`'s `result.json`, and the final code-verify artifact; commits doc updates as additional commits on the same ticket branch — not a separate PR. |
| `/acs:create-pr` | `/acs:code` completed **and** its verifier passed **and** `/acs:docs-sync` completed | Pushes the ticket branch and opens the PR (configured title/description formats, `ACS` label) against the default branch. |
| `/acs:merge-pr` | PR reference recorded; **user-invoked only** | Readiness check (CI, approvals, conflicts, protections), merge per `merge_strategy`, delete branch, mark ticket done, archive the partition. Also `/acs:merge-pr --pr <n>` (or `#n` / PR URL) to land a legitimate non-ticket **`acs-exempt`** PR — same readiness + cleanup, no ticket/partition/tracker. |
| `/acs:standardize-project` | Architecture doc set exists | Audits an EXISTING repo against `principles_path`/`standards_path`, `hld/project-structure.md`, and acs-readiness tooling (coverage/CI/pre-commit/e2e), then additively scaffolds only the missing docs/config/tooling — never moves, renames, deletes, or rewrites existing source; one reviewed PR. |

## How gating works

- **Pre-hooks are deterministic.** A `PreToolUse` hook on the `Skill` tool
  (`dispatch.py pre`) routes every `acs` skill invocation to its
  `pre-<skill>.py`. Exit 2 blocks the skill before any of its instructions
  run; stderr tells you exactly what is missing and which skill to run
  first. This fires for typed slash commands and model-initiated calls
  alike, including the step skills `/acs:ship` invokes directly.
- **Post-hooks close the loop without trusting the model.** Each skill's
  coordinator must call `post-<skill>.py --result-file …` as its mandatory
  final step; that is the only thing that flips the run to `completed`.
  Skill start has already recorded an `in_progress` run entry, and every
  downstream gate checks `runs[-1].status == "completed"` — so a skipped
  post-hook leaves the gate closed, never open.
- **A `SessionEnd` safety net** (`dispatch.py session-end`) finalizes any
  run this checkout left `in_progress` as `interrupted` and releases its
  lock, so abnormal endings still write state.

## Workspace layout

Everything durable lives under `workspace_path`, partitioned per repo and
per ticket:

```text
<workspace>/<repo-id>/                  # repo-id from git remote: owner-name
  tickets-index.json  counters.json  metrics.json
  sessions/<checkout-id>.json           # per-worktree current-ticket pointer
  archive/<ticket-id>/                  # moved here by post-merge-pr
  <ticket-id>/
    .lock  ticket.json  pipeline-state.json
    design.md  specs/NN-slug.md
    phases/<skill>/iter-<n>-<phase>.xml  phases/<skill>/result.json
    <skill>-state.json ...
```

Inspect progress and spend anytime: `tickets-index.json` for status across
tickets, `metrics.json` for per-repo totals, a ticket's
`pipeline-state.json` for where it stands in the pipeline.

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

- **"blocked — … has not completed" (skill refuses to run).** A pre-hook
  exited 2. The stderr message names the missing predecessor — run that
  skill for the same ticket (e.g. `/acs:code SHOP-123` before
  `/acs:create-pr SHOP-123` — `create-pr`'s gate additionally requires
  `/acs:docs-sync` to have completed). A "run /setup first" message means no
  `settings.json` could be resolved: run `/acs:setup`.
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
  (or is finalized `interrupted`); downstream gates simply read "not
  completed". Re-run the same skill (or `/acs:ship <ticket-id>`) — the
  coordinator sees the unfinished run and *reconciles* recorded state
  against reality (e.g. re-runs tests for specs marked implemented) before
  continuing. Phase artifacts under `phases/<skill>/` mean at most the
  in-flight phase is lost.
- **Corrupt or missing state files.** Treated as *not completed* — the gate
  stays closed rather than letting a half-recorded step pass. Re-run the
  predecessor skill for that ticket to regenerate its state.
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
