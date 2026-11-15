---
type: regex
target: { source: file, path: docs/architecture/lld/wishlist/api/wishlist-api.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?![\s\S]*\nstatus_(?:by|reason): )'
---

Only gift cards were cut: the wishlist LLD is still `approved` and carries no
`status_by` or `status_reason` -- nothing moved it.
