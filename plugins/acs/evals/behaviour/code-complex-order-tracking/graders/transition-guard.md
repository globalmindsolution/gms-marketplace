---
type: regex
target: { source: file, path: src/shop/orders.py }
pattern: 'raise\s+ValueError'
---

AC-2, the irreversible rule the plan's Risks section names: `advance` refuses a
backward or skipped transition with `ValueError`. An `orders.py` that only
assigns the new status passes the other graders and fails this one.
