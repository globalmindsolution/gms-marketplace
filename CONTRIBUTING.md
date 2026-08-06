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
  scanning, hygiene, and the `acs-free-evals` smoke) into `git commit`.

## Tests & quality

Quality is layered — see the strategy in
[docs/quality/testing-strategy.md](docs/quality/testing-strategy.md). What you'll
run day to day:

```bash
python3 -m unittest discover -s tests -v   # deterministic + contract suites (free)
python3 evals/run_evals.py                 # free behavioral smoke (gate + cleanup)
python3 evals/run_evals.py --paid          # full agentic suite — PRE-RELEASE gate ($)
```

- The **free** layers gate every commit (pre-commit) and every PR (CI). Keep
  them green — a red `acs-free-evals` hook means a gate or cleanup regression.
- The **paid** evals are a **pre-release gate**, run locally on demand (they
  cost money and are non-deterministic). Run them before bumping `version` —
  see the [release runbook](docs/operations/release-runbook.md).

### Reproducing the *Tests & coverage* gate locally

The required `Tests & coverage` check runs the exact command committed at
`.acs/settings.json`'s `tests.command`. Measurement now depends on a
committed repo-root [`.coveragerc`](.coveragerc), so reproducing the gate
locally needs a couple of extra pieces beyond the stdlib-only commands
above:

1. One-time, optional install (the stdlib-only claim above still holds for
   the default day-to-day commands — this is only needed to reproduce the
   coverage gate itself):
   ```bash
   python3 -m pip install "coverage>=7.14.2" diff-cover
   ```
2. `export ACS_COVERAGE=90` — CI's runner exports this from
   `settings.test_coverage_percent` (this repo's `.acs/settings.json` sets
   no override, so the schema default of `90` applies). Without it,
   `--fail-under` receives an empty argument locally.
3. The gate itself, byte-identical to the committed `tests.command`:
   ```bash
   export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc; python3 -m coverage run -m unittest discover -s tests && python3 -m coverage combine && python3 -m coverage xml -o coverage.xml && python3 -m diff_cover.diff_cover_tool coverage.xml --compare-branch "origin/${GITHUB_BASE_REF:-main}" --fail-under $ACS_COVERAGE
   ```
   This is **diff-scoped**: `diff-cover` grades only the lines your branch
   changes against `origin/main`, not repo-wide TOTAL. That's the gate as
   it stands today.
4. Optional diagnostic (not the gate — no `--fail-under`) for the repo-wide
   TOTAL:
   ```bash
   export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc; python3 -m coverage run -m unittest discover -s tests && python3 -m coverage combine && python3 -m coverage report
   ```
5. **Gotcha:** `.coveragerc`'s `source`/`data_file` are `${ACS_COV_ROOT}`-
   substituted absolute paths. If you run a bare `python3 -m coverage run
   ...` from the repo root without exporting `ACS_COV_ROOT` first, it
   collects **nothing** — a silent no-op, not a loud failure.

## Pull requests

- Branch off `main`; never commit directly to `main` (it's protected).
- Keep commit subjects imperative; reference the ticket id when there is one.
- CI must be green (tests on 3.9 + 3.12, pre-commit, gitleaks, version
  consistency). PRs merge **squash**.
- Touching the plugin? Update the docs it affects in the same PR — acs treats
  docs as part of the change, not an afterthought.

## Where things live

- [docs/README.md](docs/README.md) — the full-SDLC doc map (product →
  requirements → architecture → adr → quality → operations).
- [plugins/acs/docs/](plugins/acs/docs/) — implementation contract for
  contributors (INTERNALS, AUTHORING).
- [docs/product/roadmap.md](docs/product/roadmap.md) — what's planned and why.

## Dogfooding

Where practical, ship changes to this repo through acs itself
(`/acs:ship <prompt>`, or step by step from `/acs:create-ticket`) — that's
Epic E3, and it's the best behavioral coverage we have.
