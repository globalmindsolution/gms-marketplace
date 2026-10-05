---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/analysis.md }
pattern: '^-{3}\n(?:[a-z_]+:[^\n]*\n)*ticket:[ \t]*EVAL-1[ \t]*\n(?:[a-z_]+:[^\n]*\n)*-{3}'
---

A ticket run's analysis names its ticket in the machine-read front matter.
