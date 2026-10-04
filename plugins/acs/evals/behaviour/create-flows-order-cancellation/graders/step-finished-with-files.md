---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-flows/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/orders/flows/cancel-order\.md")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/orders/flows/state-order\.md")'
---

The mandatory Finish ran through `post-create-flows.py` (`completed`), and
with no ticket branch checked out `states.files` lists every written path,
repo-relative -- what /acs:analyze-requirements' publish commits with the
ticket folder.
