---
type: regex
target: { source: file, path: README.md }
pattern: '\b20\b[^\n]*per page|per page[^\n]*\b20\b'
match: not_contains
---

The old value is gone from the page-size sentence -- an update that appended a
second, contradicting line would still read "20 per page" somewhere.
