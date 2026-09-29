---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"formats"'
match: not_contains
---

All three formats were kept, and a value equal to its default is never
written.
