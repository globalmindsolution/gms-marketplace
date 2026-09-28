---
type: regex
target: { source: file, path: docs/architecture/lld/contracts.md }
pattern: '^(?![\s\S]*(?:redis|nightly-export))(?=[\s\S]*/orders)(?=[\s\S]*customer_id)(?=[\s\S]*/customers)'
flags: i
---

The contracts gain the new interface the code serves (GET /orders with
`customer_id`, src/shop/orders.py), keep the listing that still exists, and
drop the Redis `exports` queue contract.
