---
type: regex
target: files
pattern: '^(\.github/|\.pre-commit-config\.yaml|\.coveragerc|setup\.cfg|tox\.ini|pytest\.ini|ruff\.toml|docs/|\.acs/ci/)'
flags: m
match: not_contains
---

Nothing is missing, so nothing is added: no new workflow, tooling config,
doc or acs CI file.
