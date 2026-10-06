---
type: regex
target: files
pattern: '^\.acs/state-machine/example-shop/EVAL-\d+/ticket\.json$'
flags: m
match: 'count:3'
---

Only the user-confirmed children are minted -- one per design slice, no
others. new-ticket.py writes each child's ticket.json in its own workspace
partition (`.acs/state-machine/example-shop/EVAL-<n>/`); since ADR-0128 no
ticket file enters the repo.
