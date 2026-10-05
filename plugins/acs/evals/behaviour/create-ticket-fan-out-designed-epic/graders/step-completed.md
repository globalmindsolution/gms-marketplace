---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket/state.json }
pattern: '"status"\s*:\s*"completed"'
---

The fan-out is recorded as a create-ticket invocation against the epic's run
(`acs step start --step create-ticket --run EVAL-1`) and its mandatory Finish
closes it; a run left `in_progress` reports the epic mid-flight for ever.
