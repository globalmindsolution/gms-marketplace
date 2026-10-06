---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-3/ticket.json }
pattern: '"features"\s*:\s*\[\s*"order-management"\s*\]'
---

A child inherits its parent's `features` (ADR-0138): `new-ticket.py --parent`
copies them unless the confirmed breakdown narrows them.
