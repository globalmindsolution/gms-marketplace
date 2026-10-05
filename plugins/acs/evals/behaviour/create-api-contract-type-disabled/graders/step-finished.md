---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[\s*\])'
---

The mandatory Finish ran through `post-create-api-contract.py`: the invocation
is `completed` and `states.files` is empty -- a disabled type writes nothing.
