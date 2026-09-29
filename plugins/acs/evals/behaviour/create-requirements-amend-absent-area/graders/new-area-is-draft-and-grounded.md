---
type: regex
target: { source: file, path: docs/requirements/functional/order-listing.md }
pattern: '^(?=DRAFT\s*[—–-]+\s*human-confirm-required)(?=[\s\S]*\bMUST\b)(?=[\s\S]*/orders)(?=[\s\S]*customer_id)'
flags: m
---

The augmented area is a DRAFT baseline like any extracted requirement: it
opens with the marker and states MUST clauses grounded in the orders code
(GET /orders, the required `customer_id`).
