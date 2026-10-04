---
type: regex
target: { source: file, path: docs/architecture/lld/orders/flows/cancel-order.md }
pattern: '(?<![\s\S])-{3}\nstatus: "proposed"\nversion: [1-9]\d*\ntickets:\n(?:  - "[^"\n]+"\n)*?  - "EVAL-1"\n(?:  - "[^"\n]+"\n)*feature: "orders"\n-{3}\n'
---

Version front matter opening the file, as `acs.py design init --status
proposed --ticket EVAL-1 --feature orders` writes it (ADR-0122): the cancel
flow is not built, so `proposed`. Hand-written or missing front matter
fails.
