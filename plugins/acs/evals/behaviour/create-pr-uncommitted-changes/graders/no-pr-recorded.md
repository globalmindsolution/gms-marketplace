---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"pr"\s*:\s*\{'
match: not_contains
---

No PR exists, so `states.pr` is omitted -- "never a stub" (SKILL.md Finish).
