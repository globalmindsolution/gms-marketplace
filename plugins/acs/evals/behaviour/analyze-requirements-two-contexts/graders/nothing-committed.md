---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Orders and payments\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: Orders and
payments`): the run made no commit, and created, switched, reset or stashed
nothing. Only /acs:create-pr branches and commits (ADR-0127).
