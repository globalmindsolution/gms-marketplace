---
type: regex
target: files
pattern: '^(?!\.acs/)(?:src/|tests/|[^\n]*\.py$)'
flags: m
match: not_contains
---

No new source or test file: documents only. A `.pyc` cache from importing the
package is not `.py` and does not trip this.
