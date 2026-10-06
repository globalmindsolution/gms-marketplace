---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"skill"\s*:\s*"docs-sync"[^{}]*"status"\s*:\s*"open"'
---

"These questions are NEVER auto-answered": the approved-drift question is
recorded `open` (`clarify.py add` without `--answer`) -- answered, or an
assumption, would be a pick the user never made.
