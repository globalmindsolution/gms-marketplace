---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"reproduction"\s*:\s*"[^"]*list_customers'
---

The steps to reproduce land in the ticket's `reproduction` field, not only in
free prose: they name the call the report gives.
