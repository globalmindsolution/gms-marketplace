---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-test-docs"\s*:\s*\{[^{}]*"status"\s*:\s*"completed"[^{}]*"outcome"\s*:\s*"no_cases_owed"'
---

The plan owes no test cases, so the step is completed as an evidenced no-op
with the plan's reason: an answer on the ledger, not a step that silently did
not run.
