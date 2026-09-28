---
type: regex
target: files
pattern: '^docs/api/|(^|/)openapi[^/\n]*\.(ya?ml|json)$'
flags: m
match: not_contains
---

No machine-readable contract either: the repo keeps none, and this ticket owes
no surface.
