---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/task/EVAL-1-store-customers-in-sqlite$'
flags: m
---

docs-sync never creates or switches branches.
