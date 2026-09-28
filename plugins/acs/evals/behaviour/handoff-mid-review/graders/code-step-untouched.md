---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"code"\s*:\s*\{[^{}]*"status"\s*:\s*"completed"'
---

The completed `code` step stays completed. A run that took "the ticket's
work" to mean /acs:code and handed THAT off (or re-opened it) fails here.
