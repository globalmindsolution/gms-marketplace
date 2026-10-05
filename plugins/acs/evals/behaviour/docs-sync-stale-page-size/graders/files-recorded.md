---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '"files"\s*:\s*\[[^\]]*"README\.md"'
---

The step finished through `post-docs-sync.py`, which persists the result
document here, and its `files` names README.md among the docs it wrote and
left uncommitted for /acs:create-pr (ADR-0127). A run that
never ran its Finish step has no such file and fails.
