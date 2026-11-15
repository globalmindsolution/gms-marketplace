---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Customers API document \(approved\)\n$'
---

HEAD's reflog still ends at the scaffold's last entry: the run made no commit,
and created, switched, reset or stashed nothing -- each of those appends to it.
Only /acs:create-pr branches and commits (ADR-0127).
