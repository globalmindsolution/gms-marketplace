---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: 'def list_customers\(offset=0, limit=PAGE_SIZE\):\n    return \{"items": \[\], "offset": offset, "limit": limit\}'
---

standardize-project only ever adds: the existing source reads exactly as the
scaffold left it.
