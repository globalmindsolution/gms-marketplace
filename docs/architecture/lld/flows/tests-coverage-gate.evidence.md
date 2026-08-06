# Evidence sidecar — tests-coverage-gate.md

Companion `.evidence.md` file for
`docs/architecture/lld/flows/tests-coverage-gate.md`. Relocated
code-evidence citations, keyed by the body's existing heading/clause
identity, per the docs-sync sidecar convention (`docs-sync-executor.md:58-66`) ->
`[path:line]`.

- "GHA->>Runner: python3 .acs/ci/run-tests.py" / "Runner->>Runner: run
  tests.setup": `.acs/ci/run-tests.py:37-45` (reads `.acs/settings.json`'s
  `tests` block, runs `tests.setup`, exports `ACS_COVERAGE` from
  `settings.test_coverage_percent`)
- "Runner->>ParentCov: run tests.command with ACS_COV_ROOT and
  COVERAGE_PROCESS_START set": `.acs/ci/run-tests.py:55-57` (executes
  `tests.command` via `subprocess.run(command, shell=True, env=env)`)
- The committed `tests.command` itself (measurement wiring, `coverage
  combine`, `coverage xml`, `diff-cover --fail-under`):
  `.acs/settings.json:120-123`
- "TestCase->>Child: spawn subprocess.run(sys.executable, script)": the
  `run_script` helper, `tests/acs/acs_case.py:49-54`
