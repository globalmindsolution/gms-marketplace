---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"features"\s*:\s*\[\s*"'
match: not_contains
---

There is no PRD, and a technical task needs no link (ADR-0144): the ticket
names no feature. A feature slug here was invented -- no PRD declares it.
