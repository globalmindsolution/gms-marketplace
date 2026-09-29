---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"code"\s*:\s*\{[^{}]*"status"\s*:\s*"interrupted"[^{}]*"stop_reason"\s*:\s*"context_pressure"'
---

The run ledger's `code` step is finalized the way a handoff finalizes it:
`interrupted`, the one resumable status, with `stop_reason: context_pressure`
(`handed_off` is no longer a status). The scaffold left it `in_progress`.
