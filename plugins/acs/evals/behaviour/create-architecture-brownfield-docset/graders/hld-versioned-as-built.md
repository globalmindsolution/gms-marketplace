---
type: regex
target: { source: file, path: docs/architecture/hld/tech-stack.md }
pattern: '^-{3}\nstatus: "?implemented"?\nversion: [1-9]\d*\ntickets:'
---

ADR-0122: every HLD file opens with version front matter, set only through
`acs.py design init`. A new file that documents the code as built -- this
whole set, reverse-engineered from a shipped codebase -- is `status:
implemented`, version 1. The run is ticketless (ADR-0127), so `tickets` names
no delivery ticket. A file with no block, or a block written as `proposed` for
code that already exists, fails here.
