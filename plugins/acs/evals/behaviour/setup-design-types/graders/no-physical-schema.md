---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"physical-schema"'
match: not_contains
---

The user dropped the physical schema (a schemaless store).
