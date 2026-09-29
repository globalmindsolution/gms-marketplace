---
type: regex
target: { source: file, path: docs/requirements/functional/customer-listing.evidence.md }
pattern: 'src/shop/__init__\.py'
---

Brownfield clauses are code-cited, and the citations live in the area file's
companion `.evidence.md` sidecar, keyed by clause anchor, not inline in the
body. A run that wrote plausible prose without reading the code has no
sidecar to cite from.
