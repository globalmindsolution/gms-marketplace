---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '\b100\b'
---

The ticket's change: a cap of 100 on the page size. `100` appears nowhere in
the seeded module, so it can only have come from implementing EVAL-1. Read
from whichever branch the run left checked out -- ship ends on the ticket
branch, where /acs:code committed.
