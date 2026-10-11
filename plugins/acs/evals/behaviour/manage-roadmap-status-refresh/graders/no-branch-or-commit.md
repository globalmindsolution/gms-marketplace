---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: EVAL-1 Card checkout \(#12\)\n$'
---

ADR-0127: only `/acs:create-pr` branches and commits. HEAD's reflog still ends
at the scaffold's last commit, so the run created or switched no branch and
committed nothing -- the roadmap is an uncommitted change in the working tree.
