---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/api/customers.md }
pattern: '^## Surface[ \t]*$(?:(?!^## )[\s\S])*^### [^\n]*customers(?:(?!^## )[\s\S])*\bcursor\b(?:(?!^## )[\s\S])*next_cursor'
flags: m
---

`## Surface` keeps its `### ` item for GET /customers and that item now
specifies the new `cursor` parameter (AC-1) and the `next_cursor` response
field (AC-2).
