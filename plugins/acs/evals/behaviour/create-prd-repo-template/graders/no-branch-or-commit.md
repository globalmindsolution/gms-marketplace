---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Start groomr with our PRD template\n$'
---

ADR-0127: only `/acs:create-pr` branches and commits. HEAD's reflog still ends
at the scaffold's commit: the documents are uncommitted changes.
