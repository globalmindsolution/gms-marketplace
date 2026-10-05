---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract/result.json }
pattern: '"outcome"\s*:\s*"contract_written"'
---

The result document says how the step completed, and this run owes
`contract_written`: the `api-contract` LLD type is enabled by default.
