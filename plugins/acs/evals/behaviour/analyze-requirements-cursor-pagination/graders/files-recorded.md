---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/result.json }
pattern: '"files"\s*:\s*\[[^\]]*"docs/tickets/EVAL-1/analysis\.md"'
---

The result records what the run wrote and left uncommitted -- `states.files`
naming the published analysis -- because /acs:create-pr builds its commits
from those recorded paths (ADR-0127). A run that publishes without recording
leaves the file out of the PR's commit plan.
