---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: 'offset\s*<\s*0[\s\S]{0,200}raise\s+ValueError'
---

The plan's one change: a negative offset raises `ValueError` inside
`list_customers`. The scaffold's `src/shop/__init__.py` has no `raise` at all,
so a run that implemented nothing fails here.
