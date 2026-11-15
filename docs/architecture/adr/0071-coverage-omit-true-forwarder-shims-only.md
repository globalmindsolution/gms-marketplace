# 0071 — Coverage `omit` rule excludes true argument-forwarder shims only

**Status**: Accepted · **Date**: 2026-08-06

## Context

With subprocess coverage measurement fixed (ADR 0070), `plugins/acs/hooks/scripts`
contains a cluster of thin `pre-*.py`/`post-*.py` wrapper scripts — each
around 6 statements (a `sys.path` insert, an import, and a single
`run_pre`/`run_post` call, e.g. `pre-code.py`, 10 lines, no `def main()`).
Counting these against the coverage denominator adds statements that carry
no real branching logic to measure, but blanket-excluding "every `pre-*`/
`post-*` script" is not safe: `post-merge-pr.py` looks like the same shape
by name alone, but it has a real `--pr` branch
(`plugins/acs/hooks/scripts/post-merge-pr.py:21-39`) that peeks the `--pr`
flag and diverts to `lib.run_post_exempt_pr`, an exempt metrics-only path
with its own `GateError` handling, instead of the plain `lib.run_post
("merge-pr")` every other forwarder calls. Excluding it under a blanket
"argument forwarder" justification would be exactly the silent waiver PRD
G3 forbids ("coverage target met or hard-failed, never silently waived").

A second decision this record settles: where the `omit` list lives inside
`.coveragerc`. Coverage.py supports `omit` under both `[run]` (excludes at
measurement time) and `[report]` (excludes at reporting time only). Keying
either section's list on `${ACS_COV_ROOT}` looks equivalent, but a
`[report]`-section `omit` is evaluated by whatever invokes `coverage
report`/`coverage xml` — if `${ACS_COV_ROOT}` is unset in that later
step's environment, the list resolves to bare, un-prefixed relative paths
that never match any real file, silently omitting nothing.

## Decision

The coverage `omit` rule excludes **true argument-forwarder shims only**:
scripts under `plugins/acs/hooks/scripts` whose source has no `def main()`
— 15 `pre-*.py` and 14 `post-*.py` scripts, 29 total. `post-merge-pr.py` is
deliberately **not** in the list; it is measured like any other module
(21 stmts, 100% once its `--pr` branch is exercised). The list lives under
`.coveragerc`'s `[run]` section (`.coveragerc:22-51`), never `[report]`.

## Consequences

**Positive.** The omit list is honest by construction — it excludes exactly
the scripts with no logic to measure, and keeps the one forwarder-shaped
script with real behavior (`post-merge-pr.py`) fully in scope. The
shim-omitted denominator becomes 3852 stmts (4026 − 29×6) with 444 missed,
i.e. 88% — the headline figure ADR 0070 reports. Living under `[run]`
means the exclusion is evaluated at measurement time, in the same
environment (`ACS_COV_ROOT` exported) as the rest of `tests.command`, so it
can never silently degrade to "omit nothing" the way a `[report]`-section
list keyed on the same variable could.

**Accepted cost.** The list is a static enumeration, not a structural rule
("no `def main()`") coverage.py itself can apply — a future new `pre-*`/
`post-*` forwarder script must be added to `.coveragerc`'s list by hand.
`tests/acs/test_coverage_measurement_config.py`'s
`TestCoveragercOmitList` guards against drift: it re-derives the true-forwarder
set from source at test time and asserts the committed list matches it
exactly, and separately asserts `post-merge-pr.py` is never present in it.
