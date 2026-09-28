---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '"docs_committed"\s*:\s*\[[^\]]*"README\.md"'
---

The step finished through `post-docs-sync.py`, which persists the result
document here, and it names README.md among the docs it committed. A run that
never ran its Finish step has no such file and fails.
