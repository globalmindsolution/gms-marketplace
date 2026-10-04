---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/define-the-groomr-product-0a66/steps/create-prd/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/product/prd\.md")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/product/roadmap\.md")'
---

The mandatory Finish ran through the post-hook, which records the invocation
`completed` and persists the result's states. The documents stay local -- no
branch, no commit, no PR (ADR-0127) -- so `states.files` must list both documents,
repo-relative: it is exactly what `/acs:create-pr` groups and commits
later. A file written but not recorded is a change nobody was told about.
