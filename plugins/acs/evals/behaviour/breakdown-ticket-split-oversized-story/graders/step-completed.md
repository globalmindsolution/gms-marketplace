---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/breakdown-ticket/state.json }
pattern: '"status"\s*:\s*"completed"'
---

The split is recorded as a breakdown-ticket invocation against EVAL-1's run,
and its mandatory Finish closes it through the post-hook.
