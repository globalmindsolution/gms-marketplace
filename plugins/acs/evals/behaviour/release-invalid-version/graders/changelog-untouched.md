---
type: regex
target: { source: file, path: CHANGELOG.md }
pattern: '^## \[2\.5'
flags: m
match: not_contains
---

No 2.5 section of any spelling: nothing is drafted.
