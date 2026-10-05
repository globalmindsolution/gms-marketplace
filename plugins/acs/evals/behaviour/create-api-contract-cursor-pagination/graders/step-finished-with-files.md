---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/customer-listing/api/customers\.md")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/customer-listing/EVAL-1/api-contract\.md")'
---

The mandatory Finish ran through `post-create-api-contract.py`, which records
the invocation `completed` and persists the result's states: `files` lists
every written path, repo-relative -- the revised interface document and the
shared run record -- which /acs:create-pr commits in its `design` layer.
