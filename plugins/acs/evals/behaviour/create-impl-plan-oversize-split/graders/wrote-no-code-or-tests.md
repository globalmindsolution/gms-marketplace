---
type: regex
target: files
pattern: '^(src|tests|migrations)/(?![^\n]*__pycache__)'
flags: m
match: not_contains
---

The skill plans; it never implements.

Bytecode under `__pycache__/` from importing or testing the code is not
written code.
