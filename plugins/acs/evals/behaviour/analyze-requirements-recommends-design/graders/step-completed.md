---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/state.json }
pattern: '"status"\s*:\s*"completed"'
---

The mandatory Finish ran and `post-analyze-requirements.py` accepted it.
