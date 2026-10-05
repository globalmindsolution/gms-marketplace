---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/physical-schema.md }
pattern: '(?<![\s\S])-{3}\nstatus: "proposed"\nversion: [1-9]\d*\ntickets: \[\]\nfeature: "orders"\n-{3}\n'
---

Version front matter, opening the physical schema, exactly as `acs.py design init
--status proposed --feature orders` writes it on a run with no ticket
(ADR-0122, ADR-0128): `tickets: []`, never a made-up id, and the feature the
argument named. `proposed`, because nothing of the orders model is built yet.
