---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '"files"\s*:\s*\[(?=[^\]]*"README\.md")(?=[^\]]*"docs/configuration\.md")[^\]]*\]'
---

The step finished through `post-docs-sync.py`, and its `files` names both
docs it left uncommitted, repo-relative.
