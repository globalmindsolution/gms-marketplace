---
type: regex
target: files
pattern: '^(\.github/|\.pre-commit-config\.yaml|\.coveragerc|setup\.(py|cfg)|tox\.ini|ruff\.toml|\.ruff\.toml)'
flags: m
match: not_contains
---

The refusal skips the reflection loop: no CI, pre-commit, coverage or lint
config is created on an existing codebase.
