---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/physical-schema.md }
pattern: '^## Indexes and constraints[ \t]*\n(?:(?!^## )[\s\S])*\bcustomer_id\b'
flags: mi
---

The third criterion -- a shopper lists their own orders newest first, 20 per
page -- is served by an index on the order's customer key, so
`customer_id` appears under Indexes and constraints. A schema that holds the
data but not the access path the criteria need fails.
