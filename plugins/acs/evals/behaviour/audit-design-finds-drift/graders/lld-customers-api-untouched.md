---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/api/customers.md }
pattern: '^-{3}\nstatus: "implemented"\nversion: 1\ntickets:\n  - "EVAL-1"\nfeature: "customer-listing"\n-{3}\n\n# Customers API\n\n## GET /customers\n\nQuery: `offset` \(default 0\) and `limit` \(default 50\)\.\n\nResponse 200: `\{items, offset, limit\}`\.\n(?![\s\S])'
---

Read-only on the low-level design too: the drifted page size (50 here, 20
in the code) is reported with both readings and left for a person to
decide -- never silently resolved either way by editing this file.
