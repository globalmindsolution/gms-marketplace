---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-ticket/state.json }
pattern: '"status"\s*:\s*"completed"'
---

The mandatory Finish closes the create-ticket step through its post-hook.
