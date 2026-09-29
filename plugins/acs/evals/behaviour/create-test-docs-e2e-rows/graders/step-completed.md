---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-test-docs"\s*:\s*\{[^{}]*"status"\s*:\s*"completed"[^{}]*"outcome"\s*:\s*"cases_written"'
---

The mandatory Finish ran with `outcome: cases_written`.
