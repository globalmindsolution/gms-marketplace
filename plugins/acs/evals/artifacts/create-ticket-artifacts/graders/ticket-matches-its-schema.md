---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"id"\s*:\s*"EVAL-1"[\s\S]*"type"\s*:\s*"task"'
---

The ticket honours the configured prefix and records the type it was told.
`needs_design` is graded separately so a failure names which field moved.
