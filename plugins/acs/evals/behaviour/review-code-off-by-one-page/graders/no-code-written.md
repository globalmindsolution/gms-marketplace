---
type: regex
target: files
pattern: '^(src|tests)/.*\.py$'
flags: m
match: not_contains
---

No new source or test module. `.pyc` caches from a lens or adjudicator running
the code to check a claim are not `.py`, so they do not trip this; a new test
or module written by the review does.
