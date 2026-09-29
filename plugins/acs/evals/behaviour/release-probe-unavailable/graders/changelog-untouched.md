---
type: regex
target: { source: file, path: CHANGELOG.md }
pattern: '^## \[2\.5\.0\]'
flags: m
match: not_contains
---

`release_notes.py bump` writes the dated `## [2.5.0]` section. It must not
exist: the cut stops at the unanswered probe, before anything is written.
