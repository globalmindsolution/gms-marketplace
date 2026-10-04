# 0117 — One `tests` block, no Jira, and a command to migrate old settings

**Status**: Accepted · **Date**: 2026-10-03

**Supersedes**: the `test_coverage_percent`, `e2e`, `suites` and CI-gate `tests`
settings wherever earlier ADRs describe them, and Jira as a tracker backend. The
other decisions of those ADRs stand.

## Context

Test configuration lived in four places: `test_coverage_percent` (a top-level
number), `tests` (`command`/`setup` for the CI tests gate), `suites` (named
suites run by `/acs:run-e2e-tests`) and `e2e` (a deprecated alias normalized into
`suites.e2e` at load time). The alias needed a normalizer, a validator and a
collision warning; `per_iteration` was accepted on every suite and read by
nothing. Jira support was an `acli` sync path, a tracker provider, a toolchain row
and 17 files of prose that nobody on this repo uses, and which no eval covers.

ADR-0115 and ADR-0116 broke the settings shape deliberately, and a hard break is
only kind if the way across is one command.

## Decision

1. **`tests` is the one block**: `tests.coverage` (the target, default 90),
   `tests.unit` (`command`, `setup?` — the CI tests+coverage gate), `tests.e2e`,
   and any other name for a suite `/acs:run-e2e-tests` runs, each
   `{command, setup?, teardown?}`. Every key but `coverage` is a suite.
   `per_iteration` is gone.
2. **Jira is dropped.** `tracker.provider` is `local` or `github`; `tracker.jira`,
   `acli`, `--external jira:` and the Jira sync paths are gone; a ticket's
   `external.provider` is `github`. `gh` is the only tracker transport (as ADR-0088
   already required for GitHub).
3. **`acs.py settings migrate [--write]` rewrites an old file.** It covers every
   scope that exists, is a dry run by default, and maps each removed key to its
   replacement or drops it (`acs_lib.migrate_settings`).
4. **An old-shape file is refused, not ignored.** `validate_settings` raises on
   `test_coverage_percent`, `suites`, `e2e`, the old `tests.command`/`setup`, the
   old `models` tiers and Jira, naming the migrate command. A silent ignore would
   turn a configured test suite into one that quietly stops running.
   `formats`, `enforcement` and `hook_gates` (ADR-0116) stay merely ignored: they
   changed no behaviour a repo could lose without noticing.
5. **`/acs:update` runs the migration** as its post-update settings step.

## Consequences

- One place to configure tests; the alias normalizer and its warning are gone.
- Every consumer repo must run the migration once (the refusal tells them how).
- A Jira user loses sync; their provider migrates to `local`.
