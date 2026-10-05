---
type: regex
target: files
pattern: '^\.git/acs/state-machine/example-shop/[A-Z]+-\d+/ticket\.json$'
flags: m
match: not_contains
---

"The audit asks nothing and offers nothing: no ticket, no fix." The scaffold
mints no ticket, so any ticket.json is one the audit filed.
