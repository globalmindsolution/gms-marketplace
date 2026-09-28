---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '\b100\b'
---

The request's change. The scaffold's module holds no `100` anywhere, so a run
that implemented nothing -- or capped the limit somewhere other than the
library the request names -- fails here.
