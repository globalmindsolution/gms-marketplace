---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"features"\s*:\s*\[[^\]]*"order-tracking"'
---

The epic is made from the PRD and links it (ADR-0144): its `features` name
the order-tracking feature, whose own PRD is `docs/product/features/order-tracking/prd.md`.
