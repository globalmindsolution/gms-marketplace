---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Wishlist and checkout documents\n$'
---

ADR-0127: only `/acs:create-pr` branches and commits. HEAD's reflog still ends
at the scaffold's last commit, so the moved documents are uncommitted changes
in the working tree.
