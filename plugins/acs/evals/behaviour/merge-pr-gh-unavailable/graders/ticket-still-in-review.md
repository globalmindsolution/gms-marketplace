---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"status"\s*:\s*"in_review"'
---

A completed merge's post-hook marks the ticket done and archives its
partition, which moves this file away. Still here and still `in_review` means
the ticket was neither closed nor hand-edited.
