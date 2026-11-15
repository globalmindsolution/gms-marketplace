---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"pr"\s*:\s*\{'
match: not_contains
---

No PR exists, so `states.pr` must be omitted entirely -- "never a stub"
(SKILL.md Finish). A recorded pr object would open the /acs:merge-pr gate on a
PR nobody confirmed live.
