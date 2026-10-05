---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/analysis/README.md }
pattern: '^api_surface:'
flags: m
match: not_contains
---

The `api_surface` front-matter key is retired (ADR-0134): nothing reads it,
and a new analysis writes none. (A regex on a missing file fails, so this
also fails a run that published nothing.)
