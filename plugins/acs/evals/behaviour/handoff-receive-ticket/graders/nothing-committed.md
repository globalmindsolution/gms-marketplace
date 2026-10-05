---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit( \(amend\))?: '
match: not_contains
---

ADR-0127: the work arrives as uncommitted changes and stays that way. The
scaffold made only this checkout's initial commit, so any later `commit:`
line in HEAD's reflog is the run committing.
