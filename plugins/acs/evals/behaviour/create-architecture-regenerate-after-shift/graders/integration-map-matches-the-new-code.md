---
type: regex
target: { source: file, path: docs/architecture/hld/integration-map.md }
pattern: '^(?![\s\S]*(?:redis|export.worker))(?=[\s\S]*```mermaid)(?=[\s\S]*\borders\b)(?=[\s\S]*\bcustomers\b)'
flags: i
---

The API landscape is drawn from the code as it is after the shift: the new
orders API (GET /orders with `customer_id`, src/shop/orders.py) beside the
customer listing that still exists, and no Redis `exports` queue or
export-worker consumer.
