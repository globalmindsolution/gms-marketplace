---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/result.json }
pattern: '"files"\s*:\s*\[[^\]]*"docs/changes/customer-listing/EVAL-1/analysis\.md"'
---

A shared analysis is a repo change: the result records it in `states.files`,
which /acs:create-pr builds its commits from (ADR-0127).
