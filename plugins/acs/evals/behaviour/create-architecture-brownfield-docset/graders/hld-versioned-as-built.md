---
type: regex
target: { source: file, path: docs/architecture/hld/tech-stack.md }
pattern: '^-{3}\nstatus: "?implemented"?\nversion: [1-9]\d*\ntickets:(?:\n  - "?EVAL-1"?| \[[^\]\n]*EVAL-1)'
---

ADR-0122: every HLD file opens with version front matter, set only through
`acs.py design init`. A new file that documents the code as built -- this
whole set, reverse-engineered from a shipped codebase -- is `status:
implemented`, version 1, with the delivery ticket in `tickets`. A file with
no block, a block written as `proposed` for code that already exists, or
one that does not record EVAL-1 fails here.
