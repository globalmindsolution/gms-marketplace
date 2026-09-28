---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"needs_design"\s*:\s*true'
---

"Epics are always `needs_design: true` (state it, do not ask)." The
placeholder carries `false`, so a run that never materialized the epic fails.
