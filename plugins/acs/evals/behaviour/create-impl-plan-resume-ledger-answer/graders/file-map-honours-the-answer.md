---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/plan.md }
pattern: '^### Executor tasks & file map[ \t]*$(?:(?!^## )[\s\S])*src/shop/cursor\.py'
flags: m
---

C-5 -- recorded only in the ledger -- puts the codec in `src/shop/cursor.py`.
A plan whose file map omits it planned from scratch instead of from the
recorded answer ("reuse any recorded answer").
