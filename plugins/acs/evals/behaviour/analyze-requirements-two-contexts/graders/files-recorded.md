---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/result.json }
pattern: '"files"\s*:\s*\[(?=[^\]]*"docs/development/checkout-with-card-payments/EVAL-1/analysis/README\.md")(?=[^\]]*"docs/development/checkout-with-card-payments/EVAL-1/analysis/[a-z0-9]+(?:-[a-z0-9]+)*\.md")'
---

The result records every file of the published folder in `states.files` --
the README and the context files -- because /acs:create-pr builds its commits
from those recorded paths (ADR-0127).
