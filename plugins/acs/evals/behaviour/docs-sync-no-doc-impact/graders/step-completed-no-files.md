---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[\s*\])'
---

The step finished through `post-docs-sync.py` as a completed run whose
`files` is empty: the drift review agreed nothing was owed. A run that wrote
a doc lists it here; a run that never finished has no file.
