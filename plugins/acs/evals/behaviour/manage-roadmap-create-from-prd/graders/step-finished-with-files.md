---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/plan-the-roadmap-from-the-prd-dc0b/steps/manage-roadmap/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/product/roadmap\.md")'
---

The mandatory Finish ran through the post-hook, which records the invocation
`completed` and persists the result's states. The roadmap stays local -- no
branch, no commit, no PR (ADR-0127) -- so `states.files` lists it,
repo-relative: it is exactly what `/acs:create-pr` commits later.
