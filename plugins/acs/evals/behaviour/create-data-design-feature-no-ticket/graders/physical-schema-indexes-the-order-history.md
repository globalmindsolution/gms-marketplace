---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/physical-schema.md }
pattern: '^## Indexes and constraints[ \t]*\n(?:(?!^## )[\s\S])*\bcustomer_id\b'
flags: mi
---

The prompt's third requirement -- a shopper lists their own orders newest
first, 20 per page -- is served by an index on the order's customer key. A
design that read only the slug and not the prompt's requirements misses it.
