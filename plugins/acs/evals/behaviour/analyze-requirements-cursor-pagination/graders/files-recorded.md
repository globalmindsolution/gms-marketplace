---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/result.json }
pattern: '"files"\s*:\s*\[(?=[^\]]*"docs/development/customer-listing/EVAL-1/analysis/README\.md")(?=[^\]]*"docs/development/customer-listing/EVAL-1/analysis/customer-listing\.md")'
---

The result records what the run wrote and left uncommitted -- `states.files`
naming every file of the published analysis folder, the README and the context
file -- because /acs:create-pr builds its commits from those recorded paths
(ADR-0127). A run that publishes without recording leaves files out of the
PR's commit plan.
