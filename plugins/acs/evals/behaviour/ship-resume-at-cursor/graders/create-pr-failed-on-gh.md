---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-pr"\s*:\s*\{\s*"status"\s*:\s*"failed"'
---

The cursor's step ran, and ended `failed` -- the honest outcome when gh
cannot reach a forge. Absent means ship never ran the step it was resuming;
`completed` would be a PR nobody confirmed.
