---
type: regex
target: files
pattern: '^(?!\.acs/|\.claude/|\.[^/\n]+$)(?![^\n]*__pycache__)[^\n]+$'
flags: m
match: not_contains
---

No suite, no harness, no runner config, no fixture: every path the run
created is under `.acs/` (the run's own state) or `.claude/` (the session's).
Bytecode from importing the product is ignored.

A root-level dot-entry (`.bashrc`, `.gitconfig`, `.idea`, ...) is not the run's
either: Claude Code's Linux sandbox bind-mounts /dev/null over those paths
in the working directory, so they appear in every run's file list. A suite,
harness or runner config would live in a folder or carry a non-dot name.
