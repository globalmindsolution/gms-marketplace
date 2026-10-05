---
type: regex
target: { source: file, path: docs/product/features/order-tracking/analysis/README.md }
pattern: '^-{3}\n(?:[a-z_]+:[^\n]*\n)*feature:[ \t]*order-tracking[ \t]*\n(?:[a-z_]+:[^\n]*\n)*-{3}'
---

A ticketless analysis carries `feature` in place of `ticket` in its
machine-read front matter (ADR-0128), naming the feature it is filed under.
