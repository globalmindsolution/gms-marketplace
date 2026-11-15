---
type: regex
target: { source: file, path: docs/architecture/lld/orders/flows/state-order.md }
pattern: '(?<![\s\S])-{3}\nstatus: "(?:proposed|implemented)"\nversion: [1-9]\d*\ntickets:\n(?:  - "[^"\n]+"\n)*?  - "EVAL-1"\n(?:  - "[^"\n]+"\n)*feature: "orders"\n-{3}\n'
---

The state machine carries the same front matter, set through `acs.py
design`. Either status is defensible here -- most of the lifecycle is built,
the cancel transitions are not and are marked planned -- so only its
presence and shape are graded.
