---
type: regex
target: { source: file, path: docs/architecture/lld/wishlist/flows/add-item.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus_by: )'
---

The wishlist LLD's `flows/add-item.md` is part of the feature: it moves to `approved`
with the analysis, at its unchanged version 1, with `status_by` recorded.
