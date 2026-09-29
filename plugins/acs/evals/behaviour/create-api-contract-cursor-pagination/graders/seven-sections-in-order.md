---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/api-contract.md }
pattern: '^# API contract[^\n]*EVAL-1[\s\S]*^## Scope & sources[ \t]*$[\s\S]*^## Surface[ \t]*$[\s\S]*^## Error model[ \t]*$[\s\S]*^## Compatibility & versioning[ \t]*$[\s\S]*^## Examples[ \t]*$[\s\S]*^## Traceability[ \t]*$[\s\S]*^## Contract files[ \t]*$'
flags: m
---

The title names the ticket and the seven headings appear in the order
`structure_lint.py --ordered` enforces before publish.
