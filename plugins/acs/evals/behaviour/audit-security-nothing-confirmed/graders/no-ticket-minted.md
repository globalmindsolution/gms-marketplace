---
type: regex
target: files
pattern: '^\.git/acs/state-machine/example-shop/[A-Z]+-\d+/ticket\.json$'
flags: m
match: not_contains
---

The audit files no ticket -- here there is nothing to ticket at all.
