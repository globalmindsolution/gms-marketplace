---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: EVAL\-1 Only adults may check out\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: EVAL-1 Only adults may check out`): the run made no
commit, and created, switched, reset or stashed nothing -- each of those
appends to it. Only /acs:create-pr branches and commits (ADR-0127); the review changes nothing and commits nothing.
