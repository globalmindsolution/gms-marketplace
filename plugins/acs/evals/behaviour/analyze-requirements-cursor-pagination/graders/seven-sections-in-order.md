---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/analysis.md }
pattern: '^# Analysis[^\n]*EVAL-1[\s\S]*^## Problem restated[ \t]*$[\s\S]*^## Impact map[ \t]*$[\s\S]*^## Questions[ \t]*$[\s\S]*^## Assumptions[ \t]*$[\s\S]*^## Risks[ \t]*$[\s\S]*^## Refined acceptance criteria[ \t]*$[\s\S]*^## Verdict[ \t]*$'
flags: m
---

The title names the ticket and the seven headings appear in the order
`structure_lint.py --ordered` enforces before publish.
