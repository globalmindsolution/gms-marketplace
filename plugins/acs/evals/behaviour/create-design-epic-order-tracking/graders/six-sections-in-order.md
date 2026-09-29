---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/design.md }
pattern: '^# Design[^\n]*EVAL-1[\s\S]*^## Context & constraints[ \t]*$[\s\S]*^## Options considered[ \t]*$[\s\S]*^## Decision & rationale[ \t]*$[\s\S]*^## Architecture[ \t]*$[\s\S]*^## Impact & risks[ \t]*$[\s\S]*^## Rollout/migration[ \t]*$'
flags: m
---

The six required headings, in the order the structure gate checks.
