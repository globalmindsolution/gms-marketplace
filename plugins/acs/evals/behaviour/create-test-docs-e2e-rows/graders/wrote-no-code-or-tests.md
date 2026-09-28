---
type: regex
target: files
pattern: '^(src|tests)/'
flags: m
match: not_contains
---

The e2e suites are `/acs:create-e2e-tests`' to write, the unit tests
`/acs:code`'s: this skill specifies, never writes.
