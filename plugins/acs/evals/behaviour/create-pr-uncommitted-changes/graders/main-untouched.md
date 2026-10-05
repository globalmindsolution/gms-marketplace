---
type: regex
target: { source: file, path: .git/logs/refs/heads/main }
pattern: 'commit: EVAL-1'
match: not_contains
---

Never commit to the default branch: `acs.py pr commit` switches to the plan's
new branch first, carrying the working tree with it, so `main` gains no EVAL-1
commit.
