---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/main$'
flags: m
---

docs-sync never creates or switches a branch (ADR-0127). The checkout ends
where it started, on main -- not on the ticket branch a run could check out
to "find" the change.
