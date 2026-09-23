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
claude plugin marketplace add globalmindsolution/gms-marketplace@v0.5.0

# Install the acs plugin (full-shape: Claude Code agentic workflow)
claude plugin install acs@gms-marketplace

# Rolling: track the default branch — updates arrive on every version bump
claude plugin marketplace add globalmindsolution/gms-marketplace
```

(Or run `/plugin` inside a Claude Code session and install from the UI.)

**The marketplace ref is the pin.** The `acs` entry's `source` is the relative
path `./plugins/acs`: the plugin lives in this repository, beside the catalog,
and resolves from whichever commit of the marketplace you added. The entry
carries no `ref` of its own, so per-plugin pinning is gone — the gated/rolling
choice is made once, on the `marketplace add` line above, and it covers every
plugin in the catalog.

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
        "ref": "v0.5.0"
      }
    }
  }
}
```

### Devin CLI

This repo is also a **Devin plugin source** (manifest:
[`.devin-plugin/plugin.json`](.devin-plugin/plugin.json)). The repo root is a
meta-plugin whose `requiredPlugins` pull in `acs` from `plugins/acs` via a
`git-subdir` source, so installing the repo installs the plugin:

```bash
# Install the meta-plugin — pulls in acs automatically
devin plugins install globalmindsolution/gms-marketplace

# Or install just the plugin subfolder
devin plugins install globalmindsolution/gms-marketplace#plugins/acs
```

Devin loads the plugin's `skills/` and `agents/` as-is. Caveat: acs's
`hooks/hooks.json` targets Claude Code lifecycle events and tool names, so the
hook gates (skill precondition checks, the executor file-map guard, handoff
and session bookkeeping) do not fire under Devin — the pipeline runs
**ungated** there. Skills still work as instructions; enforcement is degraded.

Unlike the Claude Code entry, this `git-subdir` entry keeps a `ref` of its own,
which each release cut points at the new `v<version>` tag
(`release.extra_refs` in [`.acs/settings.json`](.acs/settings.json)) — so on the
Devin side the pin is still per-plugin.

### Releasing & updating

**Recommended: `/acs:release <version>`** — a one-command skill that drafts
and dates the CHANGELOG section from the merged-ticket archive, falling back
to `base_branch` commit history for tickets merged without an archive entry,
bumps every manifest + the Devin `ref`, and opens the exempt `release/*` PR,
then stops for a mandatory human merge (ADRs 0050-0052). The manual steps
below are the underlying mechanism it automates, and remain the documented
fallback if the skill is unavailable.

The repo ships **one shared version**: a release bumps `version` in all four
manifests `release.version_locations` lists
(`.claude-plugin/marketplace.json`, `plugins/acs/.claude-plugin/plugin.json`,
`plugins/acs/.devin-plugin/plugin.json`, `.devin-plugin/plugin.json`), points
the Devin meta-plugin's `git-subdir` `ref` at the new tag, and the Release
workflow cuts a single immutable `v<version>` tag
([CHANGELOG](plugins/acs/CHANGELOG.md)). Because the Claude Code entry
resolves `acs` from the in-repo `./plugins/acs`, the marketplace commit you
fetched *is* the plugin you get — which is exactly what makes a tag-pinned
marketplace reproducible, and why there is no separate per-plugin update. The
per-entry CI validator checks each entry's `name` (always) and `version` (only
when the entry declares one — today's `acs` entry declares none) against the
plugin's own `plugin.json`.

**Before cutting a release** (before bumping `version`), run the pre-release
gate — the commands `release.pre_release_gate` in
[`.acs/settings.json`](.acs/settings.json) lists, which `/acs:release` runs in
order and stops at the first failure:

```bash
python3 -m unittest tests.acs.test_eval_cases   # free: every eval case well-formed, every skill covered
claude plugin eval plugins/acs --tag routing --ablation none \
  --trust-plugin --no-publish --max-cost-usd 20  # PAID: does each prompt reach the right skill?
```

The second command is the plugin's eval suite — `claude plugin eval` case files
at [`plugins/acs/evals/`](plugins/acs/evals/README.md), in the layout the
[reference](https://code.claude.com/docs/en/plugin-evals) specifies. The free
check runs first on purpose: a malformed case fails it for $0 instead of being
discovered by a paid run.

Run the suite against the **installed** build too —
`claude plugin eval acs@gms-marketplace --tag routing --ablation none` grades
the installed copy with the installed copy loaded, which is what a consumer
actually runs, and is the only run that catches packaging drift. Read the
suite's README before quoting a number: it records which cases are known to be
confounded, and why. The step-by-step is the
[release runbook](docs/operations/release-runbook.md).

- **Pinned consumers** (recommended) never receive an update without an
  explicit re-pin: upgrade by re-adding the marketplace at a newer tag
  (`claude plugin marketplace add globalmindsolution/gms-marketplace@v<newer>`),
  then reload.
- **Rolling consumers** run `claude plugin marketplace update gms-marketplace` (or start a
  new session) to fetch the latest plugin versions.

Either way, **`/acs:update`** inside a session compares installed vs latest,
summarizes the changelog delta (flagging breaking changes), refreshes the
marketplace with your consent, and runs post-update migration checks
(settings schema, a leftover acs status line).

The marketplace currently ships one plugin:

- **`acs` (Autonomous Coding Skills)** — full-shape plugin targeting Claude Code.
  Provides a complete agentic software-delivery workflow: from a raw request
  through product definition (PRD), architecture, ticketing, design,
  requirements analysis, an implementation plan, an API contract and test
  cases, TDD implementation, a five-lens code review, end-to-end tests, doc
  sync, pull request, and merge. Thirty skills (`/acs:setup`,
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
  [`plugins/acs/workflows/ship.yaml`](plugins/acs/workflows/ship.yaml) — a version, a
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
| [`plugins/acs/`](plugins/acs/README.md) | The shipped plugin. `marketplace.json` resolves `acs` from `./plugins/acs`, in this tree. Its eval suite lives inside it, at [`plugins/acs/evals/`](plugins/acs/evals/README.md) — `claude plugin eval` case files, and the pre-release gate. |
| [`tests/`](tests/) | Deterministic unit + contract suites for the plugin (`python3 -m unittest discover -s tests`). |
| [`docs/`](docs/README.md) | Product, requirements, architecture, ADRs, quality and operations docs for this repo. |
| [`scripts/`](scripts/) | Repo tooling — `dev_install.py` installs this checkout as a plugin without hitting the released version's cache. |
| [`security/`](security/policy.md) | The security reporting policy, alongside the root [`SECURITY.md`](SECURITY.md). |
| [`.github/`](.github/workflows/) | CI: tests, the acs convention gate, security scans, and the release workflow that cuts the tag. |
| [`.acs/`](.acs/) | This repo's own acs configuration, CI convention gate, and run ledger. |

There is no root `evals/` folder any more. It held a golden dataset folded in
from [`globalmindsolution/acs-evals`](https://github.com/globalmindsolution/acs-evals),
a behavioural harness, and the tooling around both; all of it was retired when
the suite moved to the documented `claude plugin eval` format inside the plugin.
`git log --diff-filter=D -- evals/` finds the commit that removed it, and the
history that built the dataset stays in that repository.

## Where to read more

| Where | What |
|-------|------|
| [docs/](docs/README.md) | Product docs: [product/](docs/product/) (PRD, roadmap), [requirements/](docs/requirements/) (behavioral contract), [architecture/](docs/architecture/) (HLD/LLD), [adr/](docs/adr/) |
| [plugins/acs/README.md](plugins/acs/README.md) | acs plugin usage: install, quick start, skill reference, configuration, troubleshooting |
| [plugins/acs/docs/INTERNALS.md](plugins/acs/docs/INTERNALS.md) | acs implementation contract for contributors (lifecycle, helper CLIs, state shapes, XML rules) |
| [plugins/acs/evals/README.md](plugins/acs/evals/README.md) | The eval suite: how to run it, its tags, how routing is graded, and its known limits |
