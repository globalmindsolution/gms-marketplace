---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-api-contract"\s*:\s*\{[^{}]*"status"\s*:\s*"completed"[^{}]*"outcome"\s*:\s*"contract_written"'
---

The mandatory Finish ran with `outcome: contract_written`.
