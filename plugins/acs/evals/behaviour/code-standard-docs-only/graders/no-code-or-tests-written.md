---
type: regex
target: files
pattern: '^(src|tests)/[^\n]*\.py$'
flags: m
match: not_contains
---

The docs_only flag drops write-failing-tests-first and new-test generation,
and no source is in the map: a docs-only change creates no module under
`src/` or `tests/`. `.pyc` caches from running the existing suite are not
`.py` and do not trip this.
