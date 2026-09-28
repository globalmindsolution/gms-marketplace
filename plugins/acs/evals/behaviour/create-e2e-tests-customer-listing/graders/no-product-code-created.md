---
type: regex
target: files
pattern: '^src/[^\n]*\.py$'
flags: m
match: not_contains
---

The skill writes tests, never product code. Coarse: `files` sees only created
paths, so this catches a new module under `src/`, not an edit to `web.py`.
