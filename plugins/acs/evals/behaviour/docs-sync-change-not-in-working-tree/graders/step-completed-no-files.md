---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[\s*\])'
---

An empty changeset is an evidenced "no doc impact", never a failure: the step
finishes `completed` through `post-docs-sync.py` with an empty `files`. The
retired branch-confirmation precondition (a `failed` step over the checkout
not being the recorded branch) fails here, and so does a run that never ran
its Finish.
