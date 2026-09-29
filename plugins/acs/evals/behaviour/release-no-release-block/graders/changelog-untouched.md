---
type: regex
target: { source: file, path: CHANGELOG.md }
pattern: '^## \[2\.5\.0\]'
flags: m
match: not_contains
---

No 2.5.0 section: nothing is drafted by the helper or by hand.
