---
type: regex
target: { source: file, path: docs/product/features/customer-listing/analysis.md }
pattern: '^-{3}\n(?=(?:[a-z_]+:[^\n]*\n)*version:[ \t]*1[ \t]*\n)(?=(?:[a-z_]+:[^\n]*\n)*tickets:[ \t]*\[\][ \t]*\n)'
---

A Development run reads the feature's living analysis and never edits it:
it is still version 1, with no ticket recorded against it. A run that
published over it (re-versioning it, or adding EVAL-1 to its tickets) wrote
the delivery run's analysis into the feature's.
