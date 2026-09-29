---
type: regex
target: files
pattern: '^docs/api/|(^|/)openapi[^/\n]*\.(ya?ml|json)$|(^|/)asyncapi[^/\n]*\.(ya?ml|json)$'
flags: m
match: not_contains
---

`docs/api/` is only the fallback when a repo keeps no contracts; this one
keeps them in schemas/events/. A new OpenAPI or AsyncAPI document is a format
the repo never adopted.
