---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-api-contract":\s*\{[^{}]*"status":\s*"completed"[^{}]*"outcome":\s*"contract_written"'
---

The mandatory Finish ran with the outcome this run owes: result.json carried
`outcome: contract_written` and `post-create-api-contract.py` accepted it,
which records both on the run's step entry in run.json. A `no_surface_owed`
completion, or a step left `in_progress`, fails.
