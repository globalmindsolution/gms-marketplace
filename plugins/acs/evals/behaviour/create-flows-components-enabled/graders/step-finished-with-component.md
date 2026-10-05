---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-flows/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/orders/components/orders\.md")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/orders/flows/cancel-order\.md")(?=[\s\S]*"types"\s*:\s*\[[^\]]*"component-detail")(?=[\s\S]*"types"\s*:\s*\[[^\]]*"class")'
---

The Finish ran through the post-hook (`completed`); `states.files` lists the
component document beside the flow -- the documents stay local, and
`states.files` is the record of the changes the user is handed -- and `states.types` names both opt-in types it wrote.
