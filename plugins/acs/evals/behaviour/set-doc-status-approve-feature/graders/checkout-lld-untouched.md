---
type: regex
target: { source: file, path: docs/architecture/lld/checkout/api/checkout-api.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?proposed"?\n)(?![\s\S]*\nstatus_by: )'
---

The checkout feature was not picked: `docs/architecture/lld/checkout/api/checkout-api.md` is still `proposed` and
carries no `status_by` -- nothing moved it.
