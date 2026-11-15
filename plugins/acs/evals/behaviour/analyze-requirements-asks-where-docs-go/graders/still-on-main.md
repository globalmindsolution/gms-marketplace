---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/main$'
flags: m
---

The checkout ends where it started, on `main`: saving the team's document
choice is a settings change left in the working tree, never a commit or a
branch (ADR-0127).
