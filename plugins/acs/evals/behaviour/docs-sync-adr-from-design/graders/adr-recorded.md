---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '"docs_committed"\s*:\s*\[[^\]]*"docs/adr/0003-[^"]*\.md"'
---

The step finished through `post-docs-sync.py`, and `docs_committed` names the
new ADR, repo-relative.
