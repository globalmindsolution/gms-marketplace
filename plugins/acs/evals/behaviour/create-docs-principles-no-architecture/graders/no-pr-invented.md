---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs/result.json }
pattern: '/pull/[0-9]+'
match: not_contains
---

No PR can exist without GitHub access, so the result document carries no PR
URL.
