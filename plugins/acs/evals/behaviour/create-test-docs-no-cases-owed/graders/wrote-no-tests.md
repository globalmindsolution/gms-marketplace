---
type: regex
target: files
pattern: '^(src|tests)/'
flags: m
match: not_contains
---

A docs-only ticket gains no tests from this step.
