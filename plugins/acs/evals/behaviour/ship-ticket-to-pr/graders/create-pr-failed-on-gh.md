---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-pr"\s*:\s*\{\s*"status"\s*:\s*"failed"'
---

The cursor reached create-pr and create-pr ended `failed` -- the honest
outcome when gh cannot reach a forge. `completed` here would be a PR nobody
confirmed.
