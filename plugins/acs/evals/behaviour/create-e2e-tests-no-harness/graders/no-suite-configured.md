---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"(?:suites|e2e)"'
match: not_contains
---

The e2e command is the repo owner's to choose: the settings still configure
no suite. A run that configured one to have something to run fails here.
