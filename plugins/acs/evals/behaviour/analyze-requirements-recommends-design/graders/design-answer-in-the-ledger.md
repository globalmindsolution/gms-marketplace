---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"skill"\s*:\s*"analyze-requirements"\s*,\s*"question"\s*:\s*"[^"]*[Dd]esign'
---

A needs_design recommendation is a question until the user answers it, and
the relayed answer is recorded with `clarify.py add` BEFORE the ticket is
amended.
