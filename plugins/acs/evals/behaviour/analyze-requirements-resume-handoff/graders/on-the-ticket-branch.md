---
type: regex
target: { source: file, path: .git/HEAD }
pattern: '^ref: refs/heads/story/EVAL-1-'
---

The prior run never reached the branch step, so the resumed run creates the
ticket branch and commits the analysis there, never on `main`.
