---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: EVAL-1 Pay by card \(#21\)\n$'
---

ADR-0127: only `/acs:create-pr` branches and commits. HEAD's reflog still ends
at the scaffold's last commit: the status change is an uncommitted edit.
