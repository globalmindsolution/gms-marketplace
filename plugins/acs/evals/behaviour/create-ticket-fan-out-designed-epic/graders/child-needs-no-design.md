---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-3/ticket.json }
pattern: '^\s*"needs_design": false,?$'
flags: m
---

A child carries `needs_design: false` -- the epic carries the design, and
children inherit it.
