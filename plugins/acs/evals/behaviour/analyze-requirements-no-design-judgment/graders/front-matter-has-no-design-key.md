---
type: regex
target: { source: file, path: docs/development/order-tracking/EVAL-1/analysis/README.md }
pattern: 'needs_design'
match: not_contains
---

The README's front matter is `ticket` and `ready_for_planning` (ADR-0139): no
`needs_design_recommendation`, and no prose verdict on whether a design is
needed.
