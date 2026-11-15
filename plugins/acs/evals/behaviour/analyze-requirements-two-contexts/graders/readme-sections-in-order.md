---
type: regex
target: { source: file, path: docs/development/checkout-with-card-payments/EVAL-1/analysis/README.md }
pattern: '^# Analysis[^\n]*EVAL-1[\s\S]*^## Scope and summary[ \t]*$[\s\S]*^## Contexts[ \t]*$[\s\S]*^## Refined acceptance criteria[ \t]*$[\s\S]*^## Cross-cutting risks and decisions[ \t]*$[\s\S]*^## Questions and assumptions[ \t]*$[\s\S]*^## Verdict[ \t]*$'
flags: m
---

The README's title names the ticket and its six headings appear in the order
the controller's folder check enforces before publish.
