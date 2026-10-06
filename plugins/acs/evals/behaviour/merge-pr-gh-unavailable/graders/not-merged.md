---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/merge-pr/state.json }
pattern: '"merged"\s*:\s*true'
match: not_contains
---

`merged` is `true` only when `gh pr view` confirmed the PR `MERGED`. Nothing
could be confirmed, so the state may say `false` or say nothing -- never
`true`.
