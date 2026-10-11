---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/define-the-groomr-product-with-our-d6de/steps/create-prd/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/product/prd\.md")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/product/features/online-booking/prd\.md")'
---

The mandatory Finish ran through the post-hook, with the documents in
`states.files` for `/acs:create-pr` to commit later.
