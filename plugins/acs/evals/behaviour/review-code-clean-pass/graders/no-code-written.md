---
type: regex
target: files
pattern: '^(src|tests)/.*\.py$'
flags: m
match: not_contains
---

No new source or test module: the review judges and writes a verdict. `.pyc`
caches and coverage data from the gate's suite run are not `.py` and do not
trip this.
