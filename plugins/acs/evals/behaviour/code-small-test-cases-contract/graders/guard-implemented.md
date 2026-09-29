---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: 'limit[\s\S]{0,120}raise\s+ValueError'
---

The plan's one change: a limit below 1 raises `ValueError` inside
`list_customers`. The scaffold's module has no `raise`, so a run that wrote
only the tests fails here.
