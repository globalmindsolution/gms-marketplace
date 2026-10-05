---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/api/customers.md }
pattern: '(?<![\s\S])-{3}\nstatus: "implemented"\nversion: 1\ntickets: \[\]\nfeature: "customer-listing"\n-{3}\n'
---

The documented interface is not revised or bumped: it stays `implemented` v1,
exactly as the scaffold versioned it.
