# Coverage policy

## Target and hard-fail rule

The floor is **90%**. `.acs/ci/run-tests.py` reads it as
`settings.get("test_coverage_percent", 90)` — `.acs/settings.json` carries no
`test_coverage_percent` key, so the live floor is that documented default,
exported as `ACS_COVERAGE` into `tests.command`'s environment. A shortfall
**hard-fails** the `Tests & coverage` required check
(`.github/workflows/acs-tests.yml`) on every PR; there is no soft-warning mode.

The gate is **repo-wide**: `.acs/settings.json`'s `tests.command` ends in
`python3 -m coverage report --fail-under=$ACS_COVERAGE`
(`.acs/settings.json:122`), so the whole measured `source` tree is graded on
every PR, not just this PR's own changed lines — see
[`../architecture/lld/flows/tests-coverage-gate.md`](../architecture/lld/flows/tests-coverage-gate.md)
for its sequence diagram. Repo-wide TOTAL is **94%** (10782 statements,
598 missed, measured 2026-09-17) — above the 90 floor. It read 95% (10845 /
581) a day earlier; ADR-0095 deleted more covered code than uncovered, so the
percentage moved without any test being lost. Re-derive it directly — the same
pipeline as the gate, minus the failing `--fail-under` threshold, so it
reports the same TOTAL the gate enforces — with:

```
export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc && \
python3 -m coverage run -m unittest discover -s tests && \
python3 -m coverage combine && \
python3 -m coverage report
```

## Exclusions

Coverage is measured over two trees: `plugins/acs/hooks/scripts` — the
hook/CLI layer, `.coveragerc`'s `[run] source` — plus `evals/behavioural/`,
added as a `[run] source_dirs` entry (MAR-575; the tree has moved twice —
`evals/` → `src/acs-evals/behavioural/` → `evals/behavioural/`, where it lives
today — carrying the same files each time, so the same statements are measured
throughout). The behavioural tree is in the denominator because the eval
harness is what decides whether a paid run's misses are real findings, and it
has deterministic tests under `tests/acs/` that must not be allowed to rot; it
is a `source_dirs` entry rather than a second `source` line because
`tests/acs/test_coverage_measurement_config.py` pins `source` and `omit` to
exact values, and the hook-scripts path stays the single pinned one it has
always been. `plugins/acs/skills/**` prose and the `tests/**` tree themselves
remain unmeasured. Within the hook/CLI source, `.coveragerc`'s `omit` list
excludes the **39** pre-`*`/post-`*` argument-forwarder scripts (20 `pre-*`,
19 `post-*` — e.g. `pre-code.py`, each about 6 statements: a `sys.path`
insert, an import, and a `run_pre`/`run_post` call, no `def main()` of their
own); adding the behavioural tree changed nothing about that list and added
**no** omit entry for the eval scenario drivers. `post-merge-pr.py` is
deliberately **not** omitted: it has a real `--pr` branch and is measured,
currently at 21 statements / 100%.

`evals/behavioural/` contributes 966 of the 10782 measured statements
and 199 of the 598 missed (measured 2026-09-17; unchanged in absolute terms by
ADR-0095, which touched the plugin rather than the scenario drivers — so its
SHARE of the missed total rose, which is the same headroom finding the tabp
removal produced, reading louder; the tree was 1140 of 10925 and 317 of 702 with `behavioural/tabp/`
still in it). Split by each scenario module's declared `META["tier"]`, those
199 are **90** in free-tier drivers — deterministic, and run by the
`acs-free-evals` pre-commit hook whenever `plugins/acs/` or
`evals/behavioural/` change, just never in-process under the unit
suite — **28** in paid-tier drivers, **5** in forge-tier drivers, **59** in
`evals/behavioural/acs/harness.py` itself and **17** in the two
`run_evals.py` runners (the dispatcher and acs's own).

Note where that leaves the headroom, because the removal moved it: the
free tier is now the largest block of missed statements in the eval layer, not
the paid one. The three free drivers are $0 and deterministic — they simply run
out-of-process under the pre-commit hook rather than in-process under
`unittest`. If TOTAL ever drops under the floor, the remedy is a unit path for
those drivers, not an `omit`:
[ADR 0071](../adr/0071-coverage-omit-true-forwarder-shims-only.md) restricts
`omit` to true argument-forwarder shims, and PRD **G3** requires the target be
met or hard-failed, never silently waived.

## Measurement per stack

Single stack: Python. Coverage is measured by one job, `Tests & coverage`
in `.github/workflows/acs-tests.yml`, which installs a single unpinned
`3.x` interpreter via `actions/setup-python@v5` (`acs-tests.yml:36-38`) — no
version matrix. A separate `3.9`/`3.12` matrix runs in `.github/workflows/ci.yml`'s
`Tests & validation` job, but that job runs the plain suite
(`python3 -m unittest discover -s tests -v`, `ci.yml:32-33`) with no coverage
measurement, and it is not a required check.
`.acs/settings.json`'s `tests.command` is (shown with its `;`/`&&` chaining
kept verbatim, just line-wrapped for readability — a failing suite short-
circuits the rest via `&&`, so it never reaches `coverage report`):

```
export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc; \
python3 -m coverage run -m unittest discover -s tests && \
python3 -m coverage combine && \
python3 -m coverage report --fail-under=$ACS_COVERAGE
```

`.coveragerc`'s `parallel = true` plus the exported `COVERAGE_PROCESS_START`
gives the suite's many `subprocess.run` calls into the real hook CLIs
(`tests/acs/acs_case.py`) measurement credit, via coverage's own shipped
subprocess-startup hook; `coverage combine` then merges every child
process's parallel data file before `coverage report` grades the merged
result against `--fail-under=$ACS_COVERAGE`. `.github/workflows/acs-tests.yml`'s
`Tests & coverage` job runs this whole pipeline via `.acs/ci/run-tests.py`
on every `pull_request` (`opened`, `reopened`, `synchronize`).

## Escalation

A failing `Tests & coverage` check leaves the PR's `mergeStateStatus`
`BLOCKED` via branch protection — there is no separate notification path
beyond the GitHub check itself. Remediation is on the PR author: add or
extend tests over the whole measured `source` tree until the command
re-passes locally, then push.
There is no override or waiver mechanism, and the floor is not configurable
per-PR.
