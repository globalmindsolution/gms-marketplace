---
type: regex
target: { source: file, path: docs/product/features/order-tracking/prd.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)(?!(?:(?!\n-{3}\n)[\s\S])*\nstatus_reason:)'
---

Order tracking's requirement is named only by EVAL-2, still open, so the
feature is not implemented (ADR-0146): its PRD stays `approved` v1. A run that
forced it with `--override-delivery` -- recording a reason the user never
gave -- or hand-edited the block fails here.
