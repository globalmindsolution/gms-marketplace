---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"needs_design"'
match: not_contains
---

A ticket carries no design flag (ADR-0139). A ticket that records one means
the skill wrote a field that no longer exists.
