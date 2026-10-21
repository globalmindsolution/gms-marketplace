---
type: regex
target: files
pattern: '^(src|tests)/(?![^\n]*__pycache__)'
flags: m
match: not_contains
---

The e2e suites are `/acs:create-e2e-tests`' to write, the unit tests
`/acs:code`'s: this skill specifies, never writes.

Bytecode under `__pycache__/` from importing or testing the code is not
written code.
