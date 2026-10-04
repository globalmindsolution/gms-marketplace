---
type: regex
target: { source: file, path: docs/architecture/hld/c4-container.md }
pattern: '^-{3}\nstatus: "implemented"\nversion: 1\ntickets:\n  - "EVAL-1"\n-{3}\n\n# C4 container\n\n```mermaid\nC4Container\n  Person\(shopper, "Shopper"\)\n  Container\(shop, "shop", "Python 3", "storefront API: health and customers"\)\n  Container\(notifier, "notifier", "Python 3", "emails a shopper when their record changes"\)\n  Rel\(shopper, shop, "browses"\)\n  Rel\(shop, notifier, "POST /notifications"\)\n```\n(?![\s\S])'
---

The audit is read-only: it never edits a design document, not even one it
has just proved wrong. The container view still names the removed
`notifier`, front matter and all, byte for byte as the scaffold left it --
fixing it is /acs:create-architecture's job, from this report. The pattern
is the whole file, anchored at both ends, so any edit, a bumped version or
status, a truncation or a deletion fails it.
