---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/logical-erd.md }
pattern: '(?<![\s\S])-{3}\nstatus: "proposed"\nversion: [1-9]\d*\ntickets:\n(?:  - "[^"\n]+"\n)*?  - "EVAL-1"\n(?:  - "[^"\n]+"\n)*feature: "orders"\n-{3}\n'
---

Version front matter, opening the file, exactly as `acs.py design init
--status proposed --ticket EVAL-1 --feature orders` writes it (ADR-0122):
status, version, the tickets that touched it, and the feature. `proposed`,
because nothing of the orders model is built yet -- `implemented` is for a
document that describes the code as it is. Hand-written or missing front
matter fails.
