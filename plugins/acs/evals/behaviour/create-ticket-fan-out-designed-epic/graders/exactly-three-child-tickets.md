---
type: regex
target: files
pattern: '^docs/tickets/EVAL-\d+/ticket\.md$'
flags: m
match: 'count:3'
---

Only the user-confirmed children are minted -- one per design slice, no
others. With docs/tickets/ present, new-ticket.py writes each child as
docs/tickets/EVAL-<n>/ticket.md.
