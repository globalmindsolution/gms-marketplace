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
for its sequence diagram. Repo-wide TOTAL is **95%** (3852 statements, 174
missed) — comfortably above the 90 floor. Re-derive it directly — the same
pipeline as the gate, minus the failing `--fail-under` threshold, so it
reports the same TOTAL the gate enforces — with:

```
export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc && \
python3 -m coverage run -m unittest discover -s tests && \
python3 -m coverage combine && \
python3 -m coverage report
```

## Exclusions

Coverage is measured only over `plugins/acs/hooks/scripts` — the hook/CLI
layer. `plugins/acs/skills/**` prose and the `tests/**` tree themselves are
not measured. Within that source, `.coveragerc`'s `omit` list excludes the
**29** pre-`*`/post-`*` argument-forwarder scripts (15 `pre-*`, 14 `post-*`
— e.g. `pre-code.py`, each about 6 statements: a `sys.path` insert, an
import, and a `run_pre`/`run_post` call, no `def main()` of their own).
`post-merge-pr.py` is deliberately **not** omitted: it has a real `--pr`
branch and is measured, currently at 21 statements / 100%.

## Measurement per stack

Single stack: Python. Coverage is measured by one job, `Tests & coverage`
in `.github/workflows/acs-tests.yml`, which installs a single unpinned
`3.x` interpreter via `actions/setup-python@v5` (`acs-tests.yml:43-45`) — no
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
