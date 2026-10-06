---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-3/ticket.json }
pattern: '"needs_design"'
match: not_contains
---

A child carries no design flag (ADR-0139): a ticket records none, and the
child reads its epic's tech design, when there is one, as a found input.
