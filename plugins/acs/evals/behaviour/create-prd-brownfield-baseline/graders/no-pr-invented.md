---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-prd/result.json }
pattern: '/pull/[0-9]+'
match: not_contains
---

No PR can exist, so the result document must carry no PR URL (the skill:
"NO `states.pr` if no PR was opened"). The post-hook's own `gh pr list`
cannot run either, so a URL here is one the coordinator made up.
