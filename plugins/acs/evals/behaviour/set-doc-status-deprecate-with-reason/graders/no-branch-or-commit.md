---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Gift cards and wishlist documents\n$'
---

ADR-0127: only `/acs:create-pr` branches and commits. HEAD's reflog still ends
at the scaffold's last commit, so the deprecations are uncommitted changes in
the working tree.
