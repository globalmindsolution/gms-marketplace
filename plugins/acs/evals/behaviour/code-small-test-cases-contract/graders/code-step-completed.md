---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/code/state.json }
pattern: '"status"\s*:\s*"completed"'
---

The leg finished the step through `post-code.py`, which records the invocation
`completed` in the step's own state. The scaffold never starts `code`, so the
file does not exist until the run starts the step.
