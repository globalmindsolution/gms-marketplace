# 0070 — Fix subprocess coverage measurement instead of duplicating scenarios in-process

**Status**: Accepted · **Date**: 2026-08-06

## Context

`plugins/acs/hooks/scripts` is gated by a required "Tests & coverage" check
on `main`. The repo-wide baseline measured **62%** (4026 stmts, 1511
missed), which looked like a large genuine testing gap. It largely wasn't:
`tests/acs/acs_case.py`'s `run_script` helper drives the real hook CLIs
through `subprocess.run` — ~164 fixture-driven call sites across the
deterministic suite — and `coverage.py` does not measure subprocesses by
default (design.md:19-27). Those call sites already exercise the real CLI
contract (argv, exit codes, stdout/stderr); they just weren't getting
measurement credit for it.

Two options were weighed (design.md:128-243): duplicate every
subprocess-driven scenario as an in-process equivalent (Option A), or fix
subprocess measurement itself so the existing suite gets credit for what it
already exercises (Option B). Option B alone — `parallel=true`, an absolute
`${VAR}`-substituted `source`, `COVERAGE_PROCESS_START`, and `coverage
combine` — moved the *same* suite, zero new tests, from 62% to **87%**
(4026 stmts, 510 missed), **88%** with the 29 true argument-forwarder shims
omitted (3852 stmts, 444 missed; see ADR 0071 for the omit rule). Two
verified footguns make this fix easy to get subtly wrong: a relative
`source`/`data_file`/`COVERAGE_PROCESS_START` is never resolved by a child
process spawned at a throwaway `cwd` (`tempfile.mkdtemp()`), so measurement
silently degrades back toward ~62% with no error; and scoping the
environment assignment to only the `coverage run` segment of a `&&`-chained
command leaves `${ACS_COV_ROOT}` empty for `coverage combine`, which then
fails loudly ("No data to combine") even with populated data files on disk.

## Decision

Fix subprocess coverage measurement rather than duplicate subprocess
scenarios as in-process tests. Concretely:

- A committed repo-root `.coveragerc` with `[run] parallel = true`, an
  absolute `${ACS_COV_ROOT}`-substituted `source`, and an absolute
  `${ACS_COV_ROOT}`-substituted `data_file` (`.coveragerc:13-15`).
- `.acs/settings.json` `tests.command` exports `ACS_COV_ROOT=$PWD
  COVERAGE_PROCESS_START=$PWD/.coveragerc` across the **whole** `&&` chain
  (not just the `coverage run` segment) and inserts `python3 -m coverage
  combine` before the reporting step (`.acs/settings.json:122`).
- `.acs/settings.json` `tests.setup` pins `coverage>=7.14.2`, the version
  floor that ships coverage's own subprocess-startup hook the fix depends
  on.

This closes only the measurement gap. The residual, genuinely-untested
statements correct measurement reveals (`codeowners.py` at a literal 0%,
and smaller residual gaps in eight other modules) are a separate,
subsequent body of work tracked on MAR-168's other children — this record
covers the measurement fix alone.

## Consequences

**Positive.** Measured TOTAL moved 62% → 88% (3852 stmts / 444 missed; 87%
/ 4026 − 510 without the shim omit) with **zero change to any file under
`plugins/acs/hooks/scripts`** — the jump is a measurement-configuration
correction, not new test-writing, and it now gives the existing subprocess
suite the measurement credit it always should have had.

**Accepted cost.** +34.5% wall-clock on the coverage job (measured 47.442s
→ 63.813s), paid once per PR. Correctness now depends on coverage.py
continuing to ship and correctly install its subprocess-startup hook — a
future coverage-version regression could silently break it, mitigated but
not eliminated by the version floor. Parallel data files (`.coverage.*`)
embed absolute paths and the local username, so they must stay gitignored,
never committed.

**Guarded regressions.** Both footguns above are pinned by
`tests/acs/test_coverage_measurement_config.py`: it asserts `source` and
`data_file` are absolute and `${VAR}`-substituted (not a bare relative
path), and that the `export`/assignment in `tests.command` spans the whole
chain rather than only the `run` segment.

**Gate today.** This does not change what gates a PR — `.acs/settings.json`
`tests.command` still ends in `coverage xml` + `diff-cover`, diff-scoped
against the PR's own changed lines (`.acs/settings.json:122`). Flipping the
gate to a repo-wide `coverage report --fail-under` bar is a later, separate
change, once the residual per-module gaps above are closed.
