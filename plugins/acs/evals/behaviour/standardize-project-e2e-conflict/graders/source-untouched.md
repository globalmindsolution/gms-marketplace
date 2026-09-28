---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: 'def list_customers\(offset=0, limit=PAGE_SIZE\):\n    return \{"items": \[\], "offset": offset, "limit": limit\}'
---

Never move, rename, delete or rewrite existing source.
