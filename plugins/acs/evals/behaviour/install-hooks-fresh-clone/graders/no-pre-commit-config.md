---
type: regex
target: files
pattern: '^\.pre-commit-config\.yaml$'
flags: m
match: not_contains
---

The repo has no pre-commit config, so Step 3 takes the raw-git-hooks path;
creating one is a tracked change the user did not ask for.
