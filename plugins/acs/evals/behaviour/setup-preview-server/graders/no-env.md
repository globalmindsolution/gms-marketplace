---
type: regex
target: { source: file, path: .claude/launch.json }
pattern: '"env"'
match: not_contains
---

launch.json is committed; the user named no environment, so none is written.
