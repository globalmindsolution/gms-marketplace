---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"type"\s*:\s*"epic"'
---

A split converts the story into an epic that KEEPS ITS ID (ADR-0069,
ADR-0138): EVAL-1's own ticket becomes type `epic` before its children are
minted — `new-ticket.py --parent` refuses a parent that is not an epic.
