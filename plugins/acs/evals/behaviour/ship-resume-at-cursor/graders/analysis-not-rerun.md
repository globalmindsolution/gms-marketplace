---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/state.json }
pattern: '"started_at"'
match: count:1
---

The first step of the pipeline ran once, in the earlier session. Every `acs
step start` appends an invocation (each with its own `started_at`), so a ship
that restarted from the top instead of the cursor leaves two.
