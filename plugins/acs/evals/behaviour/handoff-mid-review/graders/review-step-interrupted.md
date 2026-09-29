---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"review-code"\s*:\s*\{[^{}]*"status"\s*:\s*"interrupted"[^{}]*"stop_reason"\s*:\s*"context_pressure"'
---

The in-flight step is the one the ledger names -- `review-code`, not the
`code` step the ticket's branch was built by -- and it is finalized the way a
handoff finalizes it: `interrupted`, `stop_reason: context_pressure`.
