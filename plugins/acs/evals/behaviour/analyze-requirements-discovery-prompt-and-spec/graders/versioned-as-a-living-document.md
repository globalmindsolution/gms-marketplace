---
type: regex
target: { source: file, path: docs/product/features/order-tracking/analysis.md }
pattern: '^-{3}\n(?=(?:[a-z_]+:[^\n]*\n)*status:[ \t]*proposed[ \t]*\n)(?=(?:[a-z_]+:[^\n]*\n)*version:[ \t]*1[ \t]*\n)'
---

The feature's living analysis is versioned like a design document (ADR-0122):
`status: proposed` and, as the feature's first analysis, `version: 1`. An
unversioned file cannot be revised in place by the next Discovery run, nor
told apart from a stale one.
