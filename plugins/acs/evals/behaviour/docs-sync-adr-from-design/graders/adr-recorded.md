---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/docs-sync/result.json }
pattern: '"files"\s*:\s*\[[^\]]*"docs/adr/0003-[^"]*\.md"'
---

The step finished through `post-docs-sync.py`, and `files` names the new
ADR it left uncommitted, repo-relative.
