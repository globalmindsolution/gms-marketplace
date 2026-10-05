---
type: regex
target: files
pattern: '^(?!\.acs/|\.git/acs/|\.claude/)[^\n]*\.md$'
flags: m
match: not_contains
---

No new doc anywhere in the repo (a refactor note, an ADR, a docs page). The
run's own notes live under `.acs/`.
