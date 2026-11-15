---
type: regex
target: files
pattern: '(^|/)(\.github/workflows/|\.acs/ci/)'
flags: m
match: not_contains
---

The request said no CI checks. Any workflow or `.acs/ci/` copy is a gate
installed without consent.
