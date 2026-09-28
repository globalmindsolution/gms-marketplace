---
type: regex
target: files
pattern: '^tests/test_[^/\n]*\.py$'
flags: m
---

TDD on a standalone run too: the implementer writes a new failing test module
before the change. The scaffold's only test is `tests/test_health.py`, which a
run does not create.
