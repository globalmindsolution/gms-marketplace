---
type: regex
target: files
pattern: '^(?!\.acs/|\.git/acs/|\.claude/)(?![^\n]*__pycache__)[^\n]+$'
flags: m
match: not_contains
---

No suite, no harness, no runner config, no fixture: every path the run
created is acs's own state (`.git/acs/`, or a legacy `.acs/`) or under
`.claude/` (the session's).
Bytecode from importing the product is ignored.
