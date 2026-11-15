---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/merge-pr/state.json }
pattern: '"merged"\s*:\s*true'
match: not_contains
---

`merged` is `true` only when the PR read confirmed the PR merged. Nothing
could be confirmed, so the state may say `false` or say nothing -- never
`true`.
