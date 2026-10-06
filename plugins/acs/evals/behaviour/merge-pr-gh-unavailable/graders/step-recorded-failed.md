---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/merge-pr/state.json }
pattern: '"status"\s*:\s*"failed"'
---

The skill finished on the failure path: a result document with status
`failed`, then `post-merge-pr.py`, which records the invocation here. A run
that never started the step has no state file (a fail); one that claimed a
merge records `completed` -- and its post-hook would have archived the run.
