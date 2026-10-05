---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-e2e-tests/result.json }
pattern: '"files"\s*:\s*\[[^\]]*"tests/e2e/[^"]+\.py"'
---

The result records the suite it wrote and left uncommitted -- `states.files`
names it -- because /acs:create-pr builds the e2e commit from those recorded
paths (ADR-0127).
