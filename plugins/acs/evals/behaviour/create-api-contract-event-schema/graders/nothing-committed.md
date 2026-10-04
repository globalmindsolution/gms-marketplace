---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Event bus with order\.created and its schema\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: Event bus with
order.created and its schema`): the run made no commit, and created, switched,
reset or stashed nothing -- each of those appends to it. Only /acs:create-pr
branches and commits (ADR-0127); whatever the step wrote stays an uncommitted
change in the working tree.
