---
type: regex
target: files
pattern: '^docs/(?!architecture/lld/README\.md$|architecture/lld/orders/README\.md$|architecture/lld/orders/flows/[^/\n]+\.md$)'
flags: m
match: not_contains
---

The only documents the skill creates are flow and state files under
lld/orders/flows/ and the feature README it creates as the first skill to
touch the feature. Never `api/` or `data/` -- other skills own those -- never
components/ when disabled, never `hld/`.
