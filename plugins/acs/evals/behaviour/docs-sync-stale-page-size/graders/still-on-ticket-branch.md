---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/task/EVAL-1-raise-the-customer-page-size-to-50$'
flags: m
---

docs-sync never creates or switches branches. The checkout ends where it
started.
