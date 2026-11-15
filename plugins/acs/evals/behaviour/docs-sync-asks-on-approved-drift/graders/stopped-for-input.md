---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"docs-sync"\s*:\s*\{[^{}]*"status"\s*:\s*"interrupted"[^{}]*"stop_reason"\s*:\s*"needs_input"'
---

Headless, the run finishes `interrupted` with `stop_reason: needs_input`
through `post-docs-sync.py`, so the resumed run re-spawns the `lld` area with
the answer -- never `completed` past an open question on an approved design.
