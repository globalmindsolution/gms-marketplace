---
type: regex
target: { source: file, path: docs/architecture/lld/order-tracking/api/order-events.md }
pattern: '(?<![\s\S])-{3}\nstatus: "proposed"\nversion: 2\ntickets:\n(?:  - "[^"\n]+"\n)*?  - "EVAL-1"\n(?:  - "[^"\n]+"\n)*feature: "order-tracking"\n(?:[a-z_]+: [^\n]*\n)*-{3}\n'
---

The feature's order-events document is revised IN PLACE and versioned exactly
as `acs.py design bump --ticket EVAL-1` writes it (ADR-0122): v1
`implemented` becomes v2 `proposed` -- order.shipped is designed, not built.
