---
type: regex
target: files
pattern: '^(\.github/|\.acs/ci/)'
flags: m
match: not_contains
---

"Don't add any CI checks."
