# Flow — tests-coverage-gate

This repo's own `Tests & coverage` required check (job name defined in
`acs-tests.yml:29`) runs `.acs/settings.json`'s `tests.command` — `coverage
combine` feeding `coverage report --fail-under`, graded repo-wide against
the whole measured `source` tree. See the companion
`tests-coverage-gate.evidence.md` sidecar for the code anchors this doc
would otherwise cite inline, and MAR-168/design.md:576-603 for the design's
own version of this diagram.

## Sequence diagram

```mermaid
sequenceDiagram
    participant GHA as GitHub Actions
    participant Runner as run-tests.py
    participant ParentCov as coverage run - parent process
    participant Suite as unittest discover
    participant TestCase as test case
    participant Child as child process
    participant PthHook as coverage pth hook
    participant DataFile as per-process data file
    participant Combine as coverage combine
    participant Report as coverage report

    GHA->>Runner: python3 .acs/ci/run-tests.py
    Runner->>Runner: run tests.setup - install coverage
    Runner->>ParentCov: run tests.command with ACS_COV_ROOT and COVERAGE_PROCESS_START set
    ParentCov->>Suite: -m unittest discover -s tests
    Suite->>TestCase: invoke test method, e.g. the run_script helper
    TestCase->>Child: spawn subprocess.run(sys.executable, script)
    Child->>PthHook: interpreter startup activates coverage's shipped pth hook
    PthHook->>DataFile: coverage.process_startup opens a new parallel data file
    Child-->>TestCase: exit code, captured stdout/stderr
    TestCase-->>Suite: assertion result
    Suite-->>ParentCov: suite result
    ParentCov->>Combine: python3 -m coverage combine
    Combine->>Report: merged data feeds coverage report, fail-under=$ACS_COVERAGE
    Report-->>GHA: TOTAL at or above 90% exits 0, below 90% exits 1, required check reflects it
```

`coverage combine` merges every child process's parallel data file
(populated via coverage's own shipped subprocess-startup hook, activated by
`COVERAGE_PROCESS_START`) before `coverage report` grades the merged
result, so the gate reflects real, subprocess-inclusive measurement instead
of an empty or parent-process-only data file. `coverage report
--fail-under=$ACS_COVERAGE` grades the whole measured `source` tree
repo-wide — not just the PR's own changed lines.

This doc covers this repo's own gate instance. The generic mechanism
(`acs-tests.yml` plus `.acs/ci/run-tests.py`, scaffolded by `/acs:initialize` for
any consumer repo) is unchanged by this measurement fix — no `plugins/`
file is touched.
