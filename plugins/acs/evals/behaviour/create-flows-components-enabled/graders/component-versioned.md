---
type: regex
target: { source: file, path: docs/architecture/lld/orders/components/orders.md }
pattern: '(?<![\s\S])-{3}\nstatus: "(?:proposed|implemented)"\nversion: [1-9]\d*\ntickets:\n(?:  - "[^"\n]+"\n)*?  - "EVAL-1"\n(?:  - "[^"\n]+"\n)*feature: "orders"\n-{3}\n'
---

The component document carries version front matter set through `acs.py
design`, like every other file the skill writes. The component is mostly
built and its cancel path is not, so either status is accepted.
