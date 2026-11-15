---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/breakdown-ticket/state.json }
pattern: '"status"\s*:\s*"completed"'
---

The breakdown is recorded as a breakdown-ticket invocation against the epic's
run (`acs step start --step breakdown-ticket --ticket EVAL-1`) and its mandatory
Finish closes it; a run left `in_progress` reports the epic mid-flight for ever.
