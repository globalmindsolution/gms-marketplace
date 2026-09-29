---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-api-contract"\s*:\s*\{[^{}]*"status"\s*:\s*"completed"[^{}]*"outcome"\s*:\s*"no_surface_owed"'
---

"That is an ANSWER on the ledger, not a step that silently did not run": the
step is recorded completed with `outcome: no_surface_owed` and the plan's
reason. A run that never invoked the skill records nothing; one that wrote a
contract records `contract_written`.
