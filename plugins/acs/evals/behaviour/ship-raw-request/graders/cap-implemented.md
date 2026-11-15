---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '\b100\b'
---

The request's change: a cap of 100. `100` appears nowhere in the seeded
module. Read from the working tree the run left: /acs:code writes it
uncommitted, and only /acs:create-pr branches and commits (ADR-0127).
