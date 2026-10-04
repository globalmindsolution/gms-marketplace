---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: PRD and roadmap\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: PRD and roadmap`): the run made no
commit, and created, switched, reset or stashed nothing -- each of those
appends to it. Only /acs:create-pr branches and commits (ADR-0127); the published design.md stays an uncommitted change in the working tree.
