---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-2/ticket.json }
pattern: '"features"\s*:\s*\[\s*"order-tracking"\s*\]'
---

A child inherits its parent's `features` (ADR-0138): `new-ticket.py --parent
EVAL-1` copies the epic's `order-tracking` slug to the child unless the
confirmed breakdown narrows it, so the child's documents land in the
feature's folders without retyping.
