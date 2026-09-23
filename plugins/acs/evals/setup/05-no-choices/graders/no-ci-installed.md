---
type: regex
target: files
pattern: '(^|/)(\.github/workflows/|\.acs/ci/)'
flags: m
match: not_contains
---

CI gates are offered, never installed silently.
