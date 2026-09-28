---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '"docs_committed"\s*:\s*\[(?=[^\]]*"README\.md")(?=[^\]]*"docs/configuration\.md")[^\]]*\]'
---

The step finished through `post-docs-sync.py`, and its `docs_committed` names
both files, repo-relative.
