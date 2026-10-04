---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/task/EVAL-1-only-adults-may-check-out$'
flags: m
---

The checkout ends where it started, on `task/EVAL-1-only-adults-may-check-out`: /acs:review-code never creates or switches
a branch (ADR-0127).
