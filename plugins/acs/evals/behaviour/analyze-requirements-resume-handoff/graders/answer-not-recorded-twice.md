---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"question"\s*:\s*"[^"]*maximum page size'
match: 'count:1'
---

"Re-asking an answered question is a defect." The ledger already holds C-3;
a run that records the maximum page size question again -- answered, assumed
or open -- asked it twice.
