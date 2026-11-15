# Evidence sidecar — tests-coverage-gate.md

Companion `.evidence.md` file for
`docs/architecture/lld/acs/flows/tests-coverage-gate.md`. Relocated
code-evidence citations, keyed by the body's existing heading/clause
identity, per the docs-sync sidecar convention (`docs-sync-doc-updater.md:61-69`) ->
`[path:line]`.

- "GHA->>Runner: python3 .acs/ci/run-tests.py": `.acs/ci/run-tests.py:37-45`
  (reads `.acs/settings.json`'s `tests` block and exports `ACS_COVERAGE`
  from `tests.coverage`)
- "Runner->>Runner: run tests.unit.setup - install coverage":
  `.acs/ci/run-tests.py:47-53` (runs `tests.unit.setup` via
  `subprocess.run(setup, shell=True, env=env)`, failing the check if setup
  exits non-zero)
- "Runner->>ParentCov: run tests.unit.command with ACS_COV_ROOT and
  COVERAGE_PROCESS_START set": `.acs/ci/run-tests.py:55-57` (executes
  `tests.unit.command` via `subprocess.run(command, shell=True, env=env)`)
- The committed `tests.unit.command` itself (measurement wiring, `coverage
  combine`, `coverage report --fail-under`): `.acs/settings.json:48`
- "TestCase->>Child: spawn subprocess.run(sys.executable, script)": the
  `run_script` helper, `tests/acs/acs_case.py:49-54`
