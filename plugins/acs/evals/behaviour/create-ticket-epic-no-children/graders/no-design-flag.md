---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"needs_design"'
match: not_contains
---

A ticket carries no design flag (ADR-0139), an epic included: the user runs
/acs:create-tech-design when they want a design, so the record states none.
