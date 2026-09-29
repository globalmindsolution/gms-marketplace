---
type: regex
target: { source: file, path: docs/quality/test-strategy.md }
pattern: '^#{1,3}\s+Testing philosophy[\s\S]*^#{1,3}\s+Coverage policy[\s\S]*^#{1,3}\s+Suite inventory[\s\S]*^#{1,3}\s+CI gates[\s\S]*^#{1,3}\s+Flaky-test policy'
flags: mi
---

The set's sentinel file, at the quality set's default location, carrying the
five sections `DOC_SETS["quality"]` requires, in order.
