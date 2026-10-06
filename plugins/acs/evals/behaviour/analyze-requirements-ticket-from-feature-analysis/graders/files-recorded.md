---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/result.json }
pattern: '"files"\s*:\s*\[[^\]]*"docs/development/customer-listing/EVAL-1/analysis/README\.md"'
---

The result records the published analysis in `states.files`, the paths
/acs:create-pr commits (ADR-0127).
