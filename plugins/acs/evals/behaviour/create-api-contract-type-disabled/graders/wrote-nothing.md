---
type: regex
target: files
pattern: '^(?!\.acs/)(?:docs/|schemas/|src/|tests/)'
flags: m
match: not_contains
---

A disabled type is never written: no interface document, no run record, no
machine-readable contract, no code.
