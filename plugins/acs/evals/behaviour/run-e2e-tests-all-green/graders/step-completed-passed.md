---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/run-e2e-tests/result.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"outcome"\s*:\s*"passed")'
---

The step's result document, persisted by `post-run-e2e-tests.py` on the
ticket's run (`runs/EVAL-1`), says the run completed with outcome `passed` --
not `no_harness` or `nothing_to_run` (two suites are configured and ran), and
not `failed`. A run that never finished the step has no such file and fails.
