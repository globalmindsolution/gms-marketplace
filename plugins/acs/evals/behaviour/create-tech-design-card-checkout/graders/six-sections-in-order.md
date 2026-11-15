---
type: regex
target: { source: file, path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/tech-design.md }
pattern: '^# Tech design[^\n]*EVAL-1[\s\S]*^## Decision & options[ \t]*$[\s\S]*^## HLD views affected[ \t]*$[\s\S]*^## LLD[ \t]*$[\s\S]*^## NFRs[ \t]*$[\s\S]*^## Risks[ \t]*$[\s\S]*^## Open questions[ \t]*$'
flags: m
---

The title names the ticket and the six headings -- derived from the
`design-default` template -- appear in order, as the reviewer's
`structure_lint.py` run requires.
