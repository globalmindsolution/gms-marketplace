---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/order-tracking/api/order-events\.md")'
---

The mandatory Finish ran through `post-create-api-contract.py`: the
invocation is `completed` and `states.files` lists the revised interface
document, repo-relative, for /acs:create-pr's `design` layer.
