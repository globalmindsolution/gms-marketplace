---
type: regex
target: { source: file, path: docs/principles/principles.md }
pattern: '^#{1,3}\s+Principles\s*$[\s\S]*^#{1,3}\s+Rationale\s*$'
flags: m
---

The set's one file, at the principles set's default location, carrying the
two sections `DOC_SETS["principles"]` requires, in order.
