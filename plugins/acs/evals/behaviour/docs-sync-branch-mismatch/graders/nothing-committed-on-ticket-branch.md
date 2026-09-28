---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-raise-the-customer-page-size-to-50 }
pattern: '\tcommit: EVAL-1 raise the customer page size to 50\n$'
---

The ticket branch's reflog still ends at /acs:code's commit. A run that
switched to it and committed the README fix -- the silent workaround -- fails
here as well as on HEAD.
