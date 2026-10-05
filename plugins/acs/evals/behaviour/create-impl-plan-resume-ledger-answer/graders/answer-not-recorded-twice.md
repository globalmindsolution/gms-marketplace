---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"question"\s*:\s*"[^"]*cursor codec'
match: 'count:1'
---

"Re-asking an answered question is a defect": C-5 is already recorded.
