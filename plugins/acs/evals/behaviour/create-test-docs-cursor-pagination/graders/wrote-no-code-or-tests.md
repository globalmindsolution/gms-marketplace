---
type: regex
target: files
pattern: '^(src|tests)/(?![^\n]*__pycache__)'
flags: m
match: not_contains
---

"You specify tests; you never write them and you never implement." The
implementers of `/acs:code` write the tests from this document.

Bytecode under `__pycache__/` from importing or testing the code is not
written code.
