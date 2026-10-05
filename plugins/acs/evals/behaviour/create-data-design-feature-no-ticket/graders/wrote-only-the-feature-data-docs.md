---
type: regex
target: files
pattern: '^docs/(?!architecture/lld/README\.md$|architecture/lld/orders/README\.md$|architecture/lld/orders/data/(?:logical-erd|physical-schema)\.md$)'
flags: m
match: not_contains
---

The only documents the skill creates are its two data documents under
lld/orders/data/ and the feature README. Never `api/`, `flows/` or `hld/`,
and no ticket docs folder of any kind.
