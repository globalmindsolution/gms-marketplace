---
type: regex
target: files
pattern: '^src/shop/orders\.py$[\s\S]*^src/shop/tracking\.py$'
flags: m
---

Both partitions' modules were created (the created-path list is sorted, so
`orders.py` precedes `tracking.py`). A run that implemented one component, or
none, fails here.
