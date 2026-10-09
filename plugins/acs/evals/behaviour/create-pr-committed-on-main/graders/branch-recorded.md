---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"branch"\s*:\s*"task/EVAL-1'
---

The step records the branch it cut in `states.branch`, "also when a later step
failed" (SKILL.md Finish): base detection failed after the branch was cut, so
the record is how a re-run and the user learn which branch to push.
