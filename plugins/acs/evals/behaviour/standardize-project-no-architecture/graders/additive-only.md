---
type: regex
target: files
pattern: '^(src|tests|docs)/[^\n]*\.(py|md)$'
flags: m
match: not_contains
---

No new source, test or doc file: the architecture set in particular is a
recommendation, never a scaffold target. (`.py`/`.md` only, so a test run's
`__pycache__` is not mistaken for authored source.)
