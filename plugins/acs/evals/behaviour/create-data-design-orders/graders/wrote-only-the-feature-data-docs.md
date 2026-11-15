---
type: regex
target: files
pattern: '^docs/(?!architecture/lld/README\.md$|architecture/lld/orders/README\.md$|architecture/lld/orders/data/(?:logical-erd|physical-schema)\.md$)'
flags: m
match: not_contains
---

The only documents the skill creates are its two data documents under
lld/orders/data/ and, as the first skill to touch the feature, the feature
README (lld/README.md already exists, so its new row is an edit). Never
`api/` or `flows/` -- other skills own those -- and never `hld/`.
