---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Reproduce the greeting typo \(red\)\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: Reproduce the
greeting typo (red)`): the run made no commit, and created, switched, reset or
stashed nothing -- each of those appends to it. Only /acs:create-pr branches
and commits (ADR-0127); the implementation stays an uncommitted change in the
working tree, its files named in the result.
