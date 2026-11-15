---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"type"\s*:\s*"bug"'
---

A report of existing behaviour that differs from what it should be is a
`bug` ticket, not a story or a task.
