---
type: regex
target: files
pattern: '^\.acs/state-machine/example-shop/EVAL-\d+/ticket\.json$'
flags: m
match: 'count:3'
---

Only the three confirmed children are minted, each in its own workspace
partition; EVAL-1 keeps its id, so no fourth ticket appears.
