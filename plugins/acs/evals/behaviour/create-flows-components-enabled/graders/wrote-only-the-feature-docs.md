---
type: regex
target: files
pattern: '^docs/(?!architecture/lld/README\.md$|architecture/lld/orders/README\.md$|architecture/lld/orders/(?:flows|components)/[^/\n]+\.md$)'
flags: m
match: not_contains
---

With the component types enabled, the skill's documents are its flows/ and
components/ files and the feature README -- still never `api/`, `data/` or
`hld/`.
