---
type: regex
target: files
pattern: '^(pyproject\.toml|setup\.(py|cfg)|\.pre-commit-config\.yaml|\.coveragerc|\.github/|tox\.ini|ruff\.toml)'
flags: m
match: not_contains
---

The refusal skips the reflection loop entirely: no build manifest, CI,
pre-commit or coverage config is written over an existing codebase.
