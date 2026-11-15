---
type: regex
target: files
pattern: '^(src|tests)/(?![^\n]*__pycache__)'
flags: m
match: not_contains
---

A docs-only ticket gains no tests from this step.

Bytecode under `__pycache__/` from importing or testing the code is not
written code.
