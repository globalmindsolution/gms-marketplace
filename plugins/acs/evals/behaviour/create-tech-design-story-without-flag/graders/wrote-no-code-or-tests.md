---
type: regex
target: files
pattern: '^(src|tests)/'
flags: m
match: not_contains
---

The design settles decisions before implementation is specified; the
coordinator publishes only tech-design.md. Production code or tests written
here skipped the pipeline.
