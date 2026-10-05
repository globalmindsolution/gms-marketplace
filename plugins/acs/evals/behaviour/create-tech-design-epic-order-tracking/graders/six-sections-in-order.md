---
type: regex
target: { source: file, path: docs/architecture/lld/order-tracking/EVAL-1/tech-design.md }
pattern: '^# Tech design[^\n]*EVAL-1[\s\S]*^## Decision & options[ \t]*$[\s\S]*^## HLD views affected[ \t]*$[\s\S]*^## LLD[ \t]*$[\s\S]*^## NFRs[ \t]*$[\s\S]*^## Risks[ \t]*$[\s\S]*^## Open questions[ \t]*$'
flags: m
---

The six required headings, in the order the structure gate checks.
