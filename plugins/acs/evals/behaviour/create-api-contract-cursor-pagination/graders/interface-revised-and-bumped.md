---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/api/customers.md }
pattern: '(?<![\s\S])-{3}\nstatus: "proposed"\nversion: 2\ntickets:\n(?:  - "[^"\n]+"\n)*?  - "EVAL-1"\n(?:  - "[^"\n]+"\n)*feature: "customer-listing"\n(?:[a-z_]+: [^\n]*\n)*-{3}\n'
---

The feature's existing interface document is revised IN PLACE and versioned
exactly as `acs.py design bump --ticket EVAL-1` writes it (ADR-0122): v1
`implemented` becomes v2 `proposed` -- the cursor is designed, not built --
with EVAL-1 among the tickets that changed it. A hand-edited block, a
skipped bump, or a second document beside it fails.
