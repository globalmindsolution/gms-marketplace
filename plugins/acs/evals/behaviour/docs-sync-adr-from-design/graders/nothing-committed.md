---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: ADRs 0001 and 0002\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: ADRs 0001 and
0002`): the run made no commit, and created, switched, reset or stashed
nothing -- each of those appends to it. Only /acs:create-pr branches and
commits (ADR-0127); the doc updates stay uncommitted beside the code change.
