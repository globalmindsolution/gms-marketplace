---
type: regex
target: files
pattern: '^docs/api/|(^|/)openapi[^/\n]*\.(ya?ml|json)$'
flags: m
match: not_contains
---

The repo keeps no machine-readable contracts, so the mode is
`no-machine-readable-contracts`: "Do NOT invent the convention". A new
`docs/api/` tree or OpenAPI document is an architecture decision the skill
must not take -- and the prompt said so.
