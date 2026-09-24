# Contributing

Thanks for working on **acs**. This repo dogfoods acs on itself, so the same
discipline acs applies to consumer repos applies here.

## Setup

- **Requirements:** `git`, `python3` ≥ 3.9 (stdlib only — no pip installs),
  `gh` authenticated. For paid evals: an authenticated `claude` CLI with the
  `acs` plugin installed.
- **Install the hooks once per clone:**
  ```bash
  pre-commit install
  ```
  This wires the repo's [pre-commit hooks](.pre-commit-config.yaml) (secret
  scanning, hygiene, and the commit-message and pre-push convention checks)
  into `git commit`.

## Tests & quality

Quality is layered — see the strategy in
[docs/quality/testing-strategy.md](docs/quality/testing-strategy.md). What you'll
run day to day:

```bash
python3 -m unittest discover -s tests -v          # deterministic + contract suites (free)
python3 -m unittest discover -s tests/evals -p 'check_*.py'   # eval-suite checks (free, local only)
cd plugins/acs && claude plugin eval . --case route-code --runs 1 --ablation none   # one eval case ($)
```

- The **free** layer gates every PR (CI). It does not include the eval suite:
  nothing about evals runs in CI (ADR-0108). The eval-suite checks under
  `tests/evals/` run locally instead — the `acs-eval-checks` pre-commit hook
  fires when a commit touches the suite, a skill or the gate, and the release
  gate runs them first. Install the hooks once per clone: `pre-commit install`.
- The **eval cases of the skills you changed** run before you open a PR, on the
  Claude subscription your `claude` CLI is logged in with. The `acs-evals`
  hook is on by default once `pre-commit install --hook-type pre-push` has
  run. It runs on `git push`, or on demand with
  `pre-commit run acs-evals --hook-stage manual`, and
  `git config acs.evals false` turns it off. See the eval suite's README,
  "Running the evals your change affects".
- The **paid** eval suite is `claude plugin eval` case files at
  [`plugins/acs/evals/`](plugins/acs/evals/README.md). Run a case or two while
  you change a skill's `description` — that is what the routing cases measure —
  and read that README for tags and known limits before quoting a number.
- The **pre-release gate** is `release.pre_release_gate` in
  [`.acs/settings.json`](.acs/settings.json): the free structural check, then
  the routing suite, then `scripts/eval_gate.py` judging it by skill rather
  than by prompt (ADR-0107), in that order. Run it before bumping `version` —
  see the [release runbook](docs/operations/release-runbook.md).

### Reproducing the *Tests & coverage* gate locally

The required `Tests & coverage` check runs the exact command committed at
`.acs/settings.json`'s `tests.command`. The floor itself, its exclusions, and
the escalation path are the normative subject of
[docs/quality/coverage-policy.md](docs/quality/coverage-policy.md) — this
section only covers reproducing the gate locally. Measurement now depends on a
committed repo-root [`.coveragerc`](.coveragerc), so reproducing the gate
locally needs a couple of extra pieces beyond the stdlib-only commands
above:

1. One-time, optional install (the stdlib-only claim above still holds for
   the default day-to-day commands — this is only needed to reproduce the
   coverage gate itself):
   ```bash
   python3 -m pip install "coverage>=7.14.2"
   ```
2. `export ACS_COVERAGE=90` — CI's runner exports this from
   `settings.test_coverage_percent` (this repo's `.acs/settings.json` sets
   no override, so the schema default of `90` applies). Without it,
   `--fail-under` receives an empty argument locally.
3. The gate itself, byte-identical to the committed `tests.command`:
   ```bash
   export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc; python3 -m coverage run -m unittest discover -s tests && python3 -m coverage combine && python3 -m coverage report --fail-under=$ACS_COVERAGE
   ```
   This is **repo-wide**: it grades the whole measured `source` tree
   against `$ACS_COVERAGE`, not just the lines your branch changes. Drop
   `--fail-under=$ACS_COVERAGE` from the same pipeline for a diagnostic
   TOTAL without failing:
   ```bash
   export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc; python3 -m coverage run -m unittest discover -s tests && python3 -m coverage combine && python3 -m coverage report
   ```
4. **Gotcha:** `.coveragerc`'s `source`/`data_file` are `${ACS_COV_ROOT}`-
   substituted absolute paths. If you run a bare `python3 -m coverage run
   ...` from the repo root without exporting `ACS_COV_ROOT` first, it
   collects **nothing** — a silent no-op, not a loud failure.

## Pull requests

- Branch off `main`; never commit directly to `main` (it's protected).
- Keep commit subjects imperative; reference the ticket id when there is one.
- Name the ticket in the PR description (`MAR-<n>`, `#<n>` or an issue link):
  it is the one rule the required `Branch / PR / commit conventions` check
  enforces. A PR no ticket stands behind carries the `acs-exempt` label.
- CI must be green (tests on 3.9 + 3.12, pre-commit, gitleaks, version
  consistency). PRs merge **squash**.
- The repo ships one shared version across four manifests:
  `.claude-plugin/marketplace.json`, `plugins/acs/.claude-plugin/plugin.json`,
  `plugins/acs/.devin-plugin/plugin.json`, and `.devin-plugin/plugin.json`.
  `/acs:release` bumps all of them via `release.version_locations` — never
  bump one by hand.
- Touching the plugin? Update the docs it affects in the same PR — acs treats
  docs as part of the change, not an afterthought.

## Where things live

- [docs/README.md](docs/README.md) — the full-SDLC doc map (product →
  requirements → architecture → adr → quality → operations).
- [plugins/acs/](plugins/acs/README.md) — the shipped plugin: skills, agents,
  hooks, workflows, schemas, templates.
- [plugins/acs/docs/](plugins/acs/docs/) — implementation contract for
  contributors (INTERNALS, AUTHORING).
- [plugins/acs/evals/README.md](plugins/acs/evals/README.md) — the eval suite:
  running it, its tags, how routing is graded, and its known limits.
- [docs/product/roadmap.md](docs/product/roadmap.md) — what's planned and why.

## Dogfooding

Where practical, ship changes to this repo through acs itself
(`/acs:ship <prompt>`, or step by step from `/acs:create-ticket`) — that's
Epic E3, and it's the best behavioral coverage we have.
