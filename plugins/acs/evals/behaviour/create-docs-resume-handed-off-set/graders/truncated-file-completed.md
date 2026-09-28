---
type: regex
target: { source: file, path: docs/quality/test-strategy.md }
pattern: '^#{1,3}\s+Testing philosophy[\s\S]*^#{1,3}\s+Coverage policy[\s\S]*^#{1,3}\s+Suite inventory[\s\S]*^#{1,3}\s+CI gates[\s\S]*^#{1,3}\s+Flaky-test policy'
flags: mi
---

The reconcile distrusts the record where it is cheap to re-check: the
handed-off test-strategy.md holds two of its five required sections, so it
counts as not done, and the resumed author completes it.
