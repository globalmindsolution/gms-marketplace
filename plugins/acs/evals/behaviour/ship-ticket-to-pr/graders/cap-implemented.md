---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '\b100\b'
---

The ticket's change: a cap of 100 on the page size. `100` appears nowhere in
the seeded module, so it can only have come from implementing EVAL-1. Read
from the working tree the run left: /acs:code writes it uncommitted, and
only /acs:create-pr branches and commits (ADR-0127).
