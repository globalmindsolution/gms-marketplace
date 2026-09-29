---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-cap-the-customer-page-size-at-100 }
pattern: '\tcommit: EVAL-1 test cases\n$'
---

The ticket branch's own reflog still ends at the scaffold's last commit: the
run committed nothing to the branch (and amended nothing).
