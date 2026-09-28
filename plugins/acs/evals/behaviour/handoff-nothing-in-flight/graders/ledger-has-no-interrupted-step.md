---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"status"\s*:\s*"interrupted"|"[\w-]+"\s*:\s*\{\s*"status"\s*:\s*"in_progress"'
match: not_contains
---

No step is left interrupted or in progress (the run itself stays `in_progress`,
which the pattern does not read as a step): the skill never runs `acs step
start` (it would open an invocation and take the lock), so it cannot have
created a step to hand off.
