---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/plan.md }
pattern: '\b90[ \t]*%|fail-under[= \t]*90\b|coverage[^\n]*\b90\b'
flags: i
---

`settings.tests.coverage` (90, the default) must be stated explicitly:
the approval predicate checks it mechanically.
