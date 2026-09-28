---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/test-cases.md }
pattern: '^# Test cases[^\n]*EVAL-1[\s\S]*^## Scope[ \t]*$[\s\S]*^## Cases[ \t]*$[\s\S]*^## Traceability[ \t]*$[\s\S]*^## Gaps and assumptions[ \t]*$'
flags: m
---

The title names the ticket and the four headings appear in the order
`structure_lint.py --ordered` enforces before publish.
