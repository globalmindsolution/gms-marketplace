---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit \(initial\): shop 2\.4\.0\n$'
---

ADR-0127: a skill never commits. HEAD's reflog still ends at the scaffold's
only commit.
