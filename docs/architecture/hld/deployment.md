# HLD — Deployment & runtime topology

```mermaid
flowchart LR
    subgraph github["GitHub"]
        MR["globalmindsolution/gms-marketplace<br/>(marketplace repo)"]
        ACT["GitHub Actions<br/>CI: tests/acs/ + tests/tabp/<br/>(per-plugin shape-conditional validation)<br/>Release: tag on version bump (via /acs:release's release/* PR + human merge)"]
        PRS["Consumer-repo PRs"]
        EVALS["evals/&lt;plugin&gt;/<br/>(local only — NOT in CI)"]
        subgraph gates["Consumer-repo required-check gates (opt-in, /acs:init-installed)"]
            G_CONV["acs-conventions.yml<br/>Branch / PR / commit conventions"]
            G_TEST["acs-tests.yml<br/>Tests & coverage"]
            G_E2E["acs-e2e.yml<br/>E2E suite"]
        end
        BP["Branch protection<br/>(required status checks, default branch)"]
    end

    subgraph machine["Developer machine"]
        CC["Claude Code<br/>(plugin host — acs)"]
        CW["Cowork<br/>(plugin host — tabp)"]
        PI_ACS["Installed acs plugin<br/>~/.claude/... (full-shape)"]
        PI_TABP["Installed tabp plugin<br/>Cowork environment (fuller shape: skills + helper + schemas + subagent charters)"]
        subgraph checkouts["Consumer repo checkouts"]
            CO1["main checkout"]
            CO2["worktree per ticket (parallel sessions)"]
        end
        WS["Workspace folder<br/>(outside every checkout)"]
        PY["python3 (stdlib) · git · gh · acli? · xmllint?"]
    end

    MR -- "claude plugin install acs@gms-marketplace" --> PI_ACS
    MR -- "claude plugin install tabp@gms-marketplace" --> PI_TABP
    MR --- ACT
    CC --> PI_ACS
    PI_ACS -- hooks/skills --> CC
    CW --> PI_TABP
    PI_TABP -- skills --> CW
    CC --> CO1 & CO2
    CO1 & CO2 -- "all pipeline state" --> WS
    CC -- "gh pr create / merge" --> PRS
    G_CONV & G_TEST & G_E2E -- "required status check" --> BP
    BP -- "mergeStateStatus" --> PRS
```

Key facts:

- **Distribution**: GitHub URL only; semver in `plugin.json`; the release
  workflow tags `v<version>` when the version bumps on `main` (updates reach
  users only on version bumps). The recommended trigger-author of that
  version-bump PR is `/acs:release <version>` — it drafts/dates the CHANGELOG
  section, bumps both manifests + `source.ref`, and opens the exempt
  `release/*` PR, then stops for a human merge; `release.yml` itself is
  reused unchanged.
- **Per-plugin install paths**: acs installs into Claude Code
  (`claude plugin install acs@gms-marketplace`); tabp installs into the Cowork
  environment (`claude plugin install tabp@gms-marketplace`). Each plugin
  targets a different runtime host.
- **One workspace, many repos**: `workspace_path` is machine-local
  (`settings.local.json`, gitignored) and may serve any number of consumer
  repos — partitions are keyed by repo identity derived from the git remote,
  so every worktree of a repo shares one partition.
- **No server-side anything**: the plugins are files; all execution happens in
  the user's Claude Code / Cowork session and shell. Tracker/PR access goes
  through the user's authenticated CLIs.
- **This repo's own CI** runs the deterministic-layer suite (Python 3.9 +
  3.12), JSON/schema validation, and the prose contract tests on every PR via
  per-plugin test discovery (`tests/acs/` and `tests/tabp/`). Behavioral evals
  (`evals/<plugin>/`) run **locally only** — they make LLM calls and are not
  coupled to CI.
- **Consumer-repo required-check gates**: `/acs:init` can opt-in scaffold up
  to three independent GitHub Actions checks per consumer repo — conventions
  (`acs-conventions.yml`), tests+coverage (`acs-tests.yml`), and e2e
  (`acs-e2e.yml`, this ticket) — each backed by a stdlib-only runner reading
  the committed `.acs/settings.json`. A committed workflow file is advisory
  until a repo admin makes its check a **required status check** on the
  protected default branch (branch protection); that is the actual
  enforcement point — a red check then leaves `mergeStateStatus BLOCKED` and
  a PR cannot merge.
  The same `acs-e2e.yml` topology is also reachable via
  `/acs:standardize-project`'s additive brownfield scaffold path for a repo
  that already exists — it adds the workflow+runner files only and never
  wires branch protection itself, so an admin still completes the gate via
  `/acs:init` (or the manual `gh api` command) afterward.
