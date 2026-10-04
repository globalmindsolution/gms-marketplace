---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/physical-schema.md }
pattern: '(?<![\s\S])-{3}\nstatus: "proposed"\nversion: [1-9]\d*\ntickets:\n(?:  - "[^"\n]+"\n)*?  - "EVAL-1"\n(?:  - "[^"\n]+"\n)*feature: "orders"\n-{3}\n'
---

The physical schema carries the same version front matter as the logical
ERD, set through `acs.py design init` with status `proposed`: the orders and
order_lines tables do not exist in migrations/ yet.
