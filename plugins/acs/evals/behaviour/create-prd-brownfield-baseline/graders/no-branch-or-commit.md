---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit \(initial\): shop 2\.4\.0\n$'
---

ADR-0127: only `/acs:create-pr` branches and commits. HEAD's reflog still ends
at the scaffold's last commit, so the run created or switched no branch and
committed nothing -- the documents are uncommitted changes in the working tree.
