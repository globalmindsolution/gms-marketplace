# GMS Marketplace

A curated catalog of Claude plugins for agentic and AI-assisted workflows.

## Prerequisites

- **Claude Code** (for the `acs` plugin) — install per the
  [official guide](https://docs.claude.com/en/docs/claude-code/overview), then
  confirm the `claude` CLI is on your `PATH` (`claude --version`).
- Each plugin has its own runtime tools (`acs` needs `git`, `python3` 3.9+,
  and an authenticated `gh`). See the per-plugin READMEs linked below for the
  full list.

## Plugin marketplace

This repository is a **Claude Code plugin marketplace** named **`gms-marketplace`**
(manifest: [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json)).
Add it and install plugins from it. Pin the marketplace to a release tag for a
controlled rollout (recommended), or omit the tag to track the latest:

```text
# Gated: pin to an immutable release tag — only an explicit re-pin upgrades you
claude plugin marketplace add globalmindsolution/gms-marketplace@v0.2.0

# Install the acs plugin (full-shape: Claude Code agentic workflow)
claude plugin install acs@gms-marketplace

# Rolling: track the default branch — updates arrive on every version bump
claude plugin marketplace add globalmindsolution/gms-marketplace
```

(Or run `/plugin` inside a Claude Code session and install from the UI.)

### Devin CLI

This repo is also a **Devin plugin source** (manifest:
[`.devin-plugin/plugin.json`](.devin-plugin/plugin.json)). The repo root is a
meta-plugin whose `requiredPlugins` pull in `acs` from `src/acs` via a
`git-subdir` source, so installing the repo installs the plugin:

```bash
# Install the meta-plugin — pulls in acs automatically
devin plugins install globalmindsolution/gms-marketplace

# Or install just the plugin subfolder
devin plugins install globalmindsolution/gms-marketplace#src/acs
```

Devin loads the plugin's `skills/` and `agents/` as-is. Caveat: acs's
`hooks/hooks.json` targets Claude Code lifecycle events and tool names, so the
hook gates (skill precondition checks, the executor file-map guard, handoff
and session bookkeeping) do not fire under Devin — the pipeline runs
**ungated** there. Skills still work as instructions; enforcement is degraded.

For a team, pin the marketplace centrally via managed settings so members
cannot drift onto unreleased versions — upgrade by changing `ref` to a
newer `v<version>` tag:

```json
{
  "extraKnownMarketplaces": {
    "gms-marketplace": {
      "source": {
        "source": "github",
        "repo": "globalmindsolution/gms-marketplace",
        "ref": "v0.2.0"
      }
    }
  }
}
```

### Releasing & updating

**Recommended: `/acs:release <version>`** — a one-command skill that drafts
and dates the CHANGELOG section from the merged-ticket archive, falling back
to `base_branch` commit history for tickets merged without an archive entry,
bumps both manifests + `source.ref`, and opens the exempt `release/*` PR,
then stops for a mandatory human merge (ADRs 0050-0052). The manual steps
below are the underlying mechanism it automates, and remain the documented
fallback if the skill is unavailable.

The catalog (`marketplace.json`) version is a marketplace-level identifier
(currently 0.2.0) and is not CI-coupled to any plugin's version. The `acs`
`plugin.json` version governs how acs updates ship. A release bumps `version`
in both `.claude-plugin/marketplace.json` and
`src/acs/.claude-plugin/plugin.json` (by convention both are kept in sync),
points the acs `git-subdir` `source.ref` at the new tag, and the Release
workflow cuts a single immutable `v<version>` tag
([CHANGELOG](src/acs/CHANGELOG.md)). acs is fetched remotely from that
pinned tag — individually updatable with `claude plugin update acs` — and
resolves reproducibly regardless of which marketplace commit is fetched. The
per-entry CI validator checks each entry's `name` (always) and `version` (only
when the entry declares one) against the plugin's own `plugin.json`.

**Before cutting a release** (before bumping `version`), run the pre-release
quality gate — **[acs-evals](src/acs-evals/README.md)** at
[`src/acs-evals/`](src/acs-evals/), not this repo's root `src/acs-evals/behavioural/` suite. Point
it at the release candidate (`ACS_PLUGIN_ROOT` at the sibling plugin source)
and run:

```bash
cd src/acs-evals
make eval-source   # deterministic golden cases against ../acs — the gate
make measure       # routing / behavioral measurement vs the promoted baseline
make perf          # performance measurement
```

Plain `make eval` resolves the newest *installed* acs build instead, which is
what a consumer actually runs. Run it **both ways**: the installed run is the
only one that catches packaging drift, and it is red by construction whenever
source is ahead of the last release.

Treat a clean `make eval-source` as the gate; investigate any failing case, and
any regression `make measure` / `make perf` reports, before tagging — the
step-by-step is the [release runbook](docs/operations/release-runbook.md). The
in-repo **paid** tier (`python3 src/acs-evals/behavioural/run_evals.py --plugin acs --paid`, which
spawns real `claude -p` sessions and needs an authenticated claude CLI) is an
**on-demand tool** kept for the forge-tier scenarios — not a gate on any ticket,
PR or release. The free tier alone (gate + cleanup smoke) already runs on every
commit via the `acs-free-evals` pre-commit hook — see
[src/acs-evals/behavioural/README.md](src/acs-evals/behavioural/README.md).

- **Pinned consumers** (recommended) never receive an update without an
  explicit re-pin: upgrade by re-pinning `ref` to a newer `v<version>` tag,
  then reload.
- **Rolling consumers** run `claude plugin marketplace update gms-marketplace` (or start a
  new session) to fetch the latest plugin versions.

Either way, **`/acs:update`** inside a session compares installed vs latest,
summarizes the changelog delta (flagging breaking changes), refreshes the
marketplace with your consent, and runs post-update migration checks
(settings schema, status-line paths).

The marketplace currently ships two plugins:

- **`acs` (Autonomous Coding Skills)** — full-shape plugin targeting Claude Code.
  Provides a complete agentic software-delivery workflow: from a raw request
  through product definition (PRD), architecture, ticketing, design,
  requirements analysis, an implementation plan, an API contract and test
  cases, TDD implementation, a five-lens code review, end-to-end tests, doc
  sync, pull request, and merge. Thirty-two skills (`/acs:setup`,
  `/acs:ship`, `/acs:code`, …), each declaring its own phase — Design, Build,
  Test, Ship or Utility — and the artifacts it reads and writes in its
  `skills/<name>/acs.yaml`; each runs an execute → verify reflection cycle
  with dedicated subagents.

  The human-facing ticket documents (`ticket.md`, `design.md`, `plan.md`,
  `test-cases.md`, …) live in the consumer repo under
  `docs/tickets/<ticket-id>/`, reviewable in the PR like any other doc; the
  durable **run ledger** lives in a gitignored `.acs/state-machine` folder
  inside the consumer repo by default (an explicit override can still point
  it elsewhere), making runs resumable and tickets shippable in parallel
  across git worktrees.

  The delivery **order** is declared in
  [`src/acs/workflows/ship.yaml`](src/acs/workflows/ship.yaml) — a version, a
  flat list of skill names and one `loops:` entry, and deliberately nothing
  more: no conditions, no `needs:`, no per-step keys. A consumer can replace
  it wholesale with its own `.acs/workflows/ship.yaml`. Every step runs on
  every run; a step that owes nothing records an evidenced no-op from the
  plan's `## Contract` block rather than being skipped by a predicate, which
  is what keeps each skill runnable on its own — a skill whose applicability
  a workflow decided for it could not be trusted when invoked by hand.
  `/acs:ship <ticket-id>` is a thin loop over `acs.py run next`, the run's
  derived cursor. **`/acs:ship` takes a ticket id** — a new request starts in
  the Design phase with `/acs:create-ticket`. Each skill's pre/post hooks
  check only the *inputs* that skill reads plus a couple of *safety brakes*,
  so running one out of the declared order prints a one-line advisory, never
  a refusal.

## Repository layout

| Path | What lives there |
|------|------------------|
| [`src/acs/`](src/acs/README.md) | The shipped plugin. `marketplace.json` resolves `acs` from `src/acs` at the pinned release tag. |
| [`tests/`](tests/) | Deterministic unit + contract suites for the plugin (`python3 -m unittest discover -s tests`). |
| [`src/acs-evals/`](src/acs-evals/README.md) | The **golden dataset** — the pre-release gate. Replays recorded CLI invocations against a *built* plugin and fails on any drift. Folded in from `globalmindsolution/acs-evals` (squash-merged; see below). |
| [`src/acs-evals/behavioural/`](src/acs-evals/behavioural/README.md) | Behavioural scenarios that spawn real `claude -p` sessions. Free tier gates every commit; paid tier is on demand. Was the repo-root `evals/` tree. |
| [`docs/`](docs/README.md) | Product, requirements, architecture, ADRs, quality and operations docs for this repo. |
| [`.acs/`](.acs/) | This repo's own acs configuration, CI convention gate, and run ledger. |

`src/acs-evals/` keeps its own `Makefile`, `README.md` and `docs/` — read those
before running it. It arrived by squash merge, so `git log -- src/acs-evals/`
shows a single commit; the history that built it stays in
[`globalmindsolution/acs-evals`](https://github.com/globalmindsolution/acs-evals)
under the old repo-root-relative paths. `src/acs-evals/README.md` has the two
commands for reading it.

## Where to read more

| Where | What |
|-------|------|
| [docs/](docs/README.md) | Product docs: [product/](docs/product/) (PRD, roadmap), [requirements/](docs/requirements/) (behavioral contract), [architecture/](docs/architecture/) (HLD/LLD), [adr/](docs/adr/) |
| [src/acs/README.md](src/acs/README.md) | acs plugin usage: install, quick start, skill reference, configuration, troubleshooting |
| [src/acs/docs/INTERNALS.md](src/acs/docs/INTERNALS.md) | acs implementation contract for contributors (lifecycle, helper CLIs, state shapes, XML rules) |
