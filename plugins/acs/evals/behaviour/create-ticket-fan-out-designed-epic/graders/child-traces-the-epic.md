---
type: regex
target: { source: file, path: docs/tickets/EVAL-2/ticket.md }
pattern: '^parent: "EVAL-1"\n(?:[a-z_]+:[^\n]*\n|  [^\n]*\n)*needs_design: false$'
flags: m
---

Each child records the epic as its `parent` and carries `needs_design:
false` -- the epic carries the design, and children inherit it.
