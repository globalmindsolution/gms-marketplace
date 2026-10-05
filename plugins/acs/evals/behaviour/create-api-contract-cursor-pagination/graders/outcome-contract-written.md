---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract/result.json }
pattern: '"outcome"\s*:\s*"contract_written"'
---

The result document says how the step completed -- the post-hook refuses a
completed one without an outcome -- and this run owes `contract_written`: the
`api-contract` LLD type is enabled by default, so `type_disabled` is wrong.
(`step-finished-with-files` proves the post-hook accepted this document.)
