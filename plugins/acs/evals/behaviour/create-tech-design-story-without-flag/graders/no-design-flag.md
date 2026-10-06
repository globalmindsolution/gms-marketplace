---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"needs_design"'
match: not_contains
---

A ticket carries no design flag (ADR-0139). Writing one onto the ticket --
to "unlock" the skill, or to record that a design now exists -- revives a
field that no longer means anything.
