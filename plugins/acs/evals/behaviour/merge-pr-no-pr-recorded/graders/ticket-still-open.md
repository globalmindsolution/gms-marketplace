---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"status"\s*:\s*"open"'
---

A completed merge's post-hook marks the ticket done and archives the
partition, moving this file. Still here and still `open` means nothing
closed the ticket.
