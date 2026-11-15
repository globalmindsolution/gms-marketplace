---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/data/physical-schema.md }
pattern: '^-{3}\nstatus: [^\n]*\nversion: 1\n'
---

A flip is a status move, not an edit: nothing in the document needed changing,
so it was never bumped (`acs.py design bump` would make it `proposed` v2 and
re-open it for approval).
