---
type: regex
target: { source: file, path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/design.md }
pattern: '^# Design[^\n]*EVAL-1[\s\S]*^## Context & constraints[ \t]*$[\s\S]*^## Options considered[ \t]*$[\s\S]*^## Decision & rationale[ \t]*$[\s\S]*^## Architecture[ \t]*$[\s\S]*^## Impact & risks[ \t]*$[\s\S]*^## Rollout/migration[ \t]*$'
flags: m
---

The title names the ticket and the six headings -- derived from the
`design-default` template -- appear in order, as the design
reviewer's `structure_lint.py` run requires.
