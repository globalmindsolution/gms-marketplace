---
type: regex
target: files
pattern: 'acs-(tests|conventions)\.yml|check-conventions\.py|run-tests\.py'
match: not_contains
---

Only the e2e gate was asked for.
