---
type: regex
target: files
pattern: '^(?:tests|src)/(?![^\n]*__pycache__)[^\n]+$'
flags: m
match: not_contains
---

Nothing owed, nothing written: no new file under `tests/` (an e2e suite
written anyway) or `src/`. Bytecode from running a suite is ignored.
