---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '"status"\s*:\s*"failed"'
---

Finish is "MANDATORY ... never skipped, including on failure": the step ends
`failed` through `post-docs-sync.py`, so the ledger does not claim a docs sync
that never ran. (A pre-hook refusal would leave no result at all; this gate
passes -- the mismatch is the coordinator's own check.)
