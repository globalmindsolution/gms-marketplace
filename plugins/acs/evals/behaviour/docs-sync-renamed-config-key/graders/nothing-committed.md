---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Environment configuration and its docs\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: Environment
configuration and its docs`): the run made no commit, and created, switched,
reset or stashed nothing -- each of those appends to it. Only /acs:create-pr
branches and commits (ADR-0127); the doc updates stay uncommitted beside the
code change.
