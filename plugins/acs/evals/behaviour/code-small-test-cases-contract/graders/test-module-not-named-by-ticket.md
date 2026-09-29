---
type: regex
target: files
pattern: '^tests/[^\n]*(?:EVAL|eval_1)'
flags: mi
match: not_contains
---

Test modules are named by the behaviour under test, never by a ticket id; the
ticket reference lives in the module docstring (execute.md, step 2).
