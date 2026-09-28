---
type: regex
target: { source: file, path: .git/hooks/pre-push }
pattern: 'check-conventions'
match: not_contains
---

"Don't overwrite it and don't merge anything into it": the installer never
clobbers a non-acs hook, and the user refused a hand merge.
