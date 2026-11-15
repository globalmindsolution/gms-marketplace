---
type: regex
target: files
pattern: '^(?:docs/|(?:src|tests)/.*\.py$)'
flags: m
match: not_contains
---

Read-only: no document, test or source file is created. In particular the
audit does not draw the missing hld/data-flow.md itself so the threat-model
slice has something to read -- that is /acs:create-architecture's job, once
/acs:setup enables the view.
