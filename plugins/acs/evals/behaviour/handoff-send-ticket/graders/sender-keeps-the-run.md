---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"code"\s*:\s*\{[^{}]*"status"\s*:\s*"in_progress"'
---

A handoff is a copy, not a pause: the sender's code step stays `in_progress`.
A run that finalized it (the retired session handoff's `interrupted`) or
abandoned the run fails here.
