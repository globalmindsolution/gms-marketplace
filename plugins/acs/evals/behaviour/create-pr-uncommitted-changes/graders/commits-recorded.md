---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"commits"\s*:\s*\[\s*\{'
---

The step records the commits it made in `states.commits` "whenever it made
any, also when a later step failed" (SKILL.md Finish) -- here base detection
failed after the commit phase, so the record is the only place a re-run and
the user learn what already exists.
