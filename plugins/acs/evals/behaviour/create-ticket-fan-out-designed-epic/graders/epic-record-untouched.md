---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"title"\s*:\s*"Order tracking"[\s\S]*"type"\s*:\s*"epic"'
---

In `--fan-out` mode Steps 1-3 do not run: the epic's own record is never
re-analyzed or rewritten, only its `children` change.
