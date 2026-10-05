---
type: regex
target: files
pattern: '^\.git/acs/state-machine/example-shop/EVAL-\d+/ticket\.json$'
flags: m
match: not_contains
---

The request says to ticket nothing, so the one grouped "which gaps to
ticket" choice is answered no: EVAL-1 (the scaffold's) is the only ticket.
