---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '(?<![\s\S])PAGE_SIZE = 20\n\n\ndef health\(\):\n    return "ok"\n\n\ndef list_customers\(offset=0, limit=PAGE_SIZE\):\n    return \{"items": \[\], "offset": offset, "limit": limit\}\n(?![\s\S])'
---

The skill specifies; /acs:code implements. `list_customers` is byte for byte
as the scaffold left it -- no cursor implemented "while we are here".
