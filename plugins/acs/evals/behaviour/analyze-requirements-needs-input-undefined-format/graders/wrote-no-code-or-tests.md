---
type: regex
target: files
pattern: '^(src|tests)/(?![^\n]*__pycache__)'
flags: m
match: not_contains
---

The skill analyzes; it never implements -- least of all an export in a
format nobody chose.

Bytecode under `__pycache__/` from importing or testing the code is not
written code.
