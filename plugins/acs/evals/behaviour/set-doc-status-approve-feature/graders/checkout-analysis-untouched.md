---
type: regex
target: { source: file, path: docs/product/features/checkout/analysis.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?proposed"?\n)(?![\s\S]*\nstatus_by: )'
---

The checkout feature was not picked: `docs/product/features/checkout/analysis.md` is still `proposed` and
carries no `status_by` -- nothing moved it.
