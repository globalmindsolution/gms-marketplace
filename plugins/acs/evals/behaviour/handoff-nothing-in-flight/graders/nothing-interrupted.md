---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"code"\s*:\s*\{[^{}]*"status"\s*:\s*"completed"'
---

The completed `code` step is left exactly as recorded. A run that forced a
step to `interrupted` -- or re-opened `code` with `acs step start` and handed
it off -- fails here.
