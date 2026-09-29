---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"suites"\s*:\s*\{\s*"e2e"\s*:\s*\{\s*"command"\s*:\s*"python3 -m pytest -q e2e"'
---

The gate runs the configured suite, so its definition stays as the team
wrote it.
