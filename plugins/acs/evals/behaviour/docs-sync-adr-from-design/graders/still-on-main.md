---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/main$'
flags: m
---

The checkout ends where it started, on `main`: /acs:docs-sync never creates or switches
a branch (ADR-0127).
