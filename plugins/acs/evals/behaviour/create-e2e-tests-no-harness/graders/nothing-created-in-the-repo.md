---
type: regex
target: files
pattern: '^(?!\.acs/|\.claude/)(?![^\n]*__pycache__)[^\n]+$'
flags: m
match: not_contains
---

No suite, no harness, no runner config, no fixture: every path the run
created is under `.acs/` (the run's own state) or `.claude/` (the session's).
Bytecode from importing the product is ignored.
