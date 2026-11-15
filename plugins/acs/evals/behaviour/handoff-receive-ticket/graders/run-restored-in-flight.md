---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"code"\s*:\s*\{[^{}]*"status"\s*:\s*"in_progress"'
---

The run ledger arrived as Lan left it: the code step still `in_progress`, so
`/acs:code EVAL-1` resumes it here. A run that re-created the run some other
way, or finalized the step, fails here.
