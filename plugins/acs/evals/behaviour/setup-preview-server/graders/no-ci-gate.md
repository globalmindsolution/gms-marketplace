---
type: regex
target: files
pattern: 'acs-(tests|conventions|e2e)\.yml|check-conventions\.py|run-tests\.py|run-e2e\.py'
match: not_contains
---

The user said not to add any CI check.
