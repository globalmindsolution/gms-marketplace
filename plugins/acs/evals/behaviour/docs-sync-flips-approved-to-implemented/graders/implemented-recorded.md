---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/state.json }
pattern: '"implemented"\s*:\s*\[\s*"docs/architecture/lld/customer-listing/data/physical-schema\.md"\s*\]'
---

The step finished through `post-docs-sync.py` with the flipped document in
`states.implemented` -- a list the post-hook keeps only for a path whose front
matter reads `implemented`.
