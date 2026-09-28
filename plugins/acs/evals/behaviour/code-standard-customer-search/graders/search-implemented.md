---
type: regex
target: { source: file, path: src/shop/search.py }
pattern: 'def\s+search_customers\s*\(\s*customers\s*,\s*query'
---

Task 1's deliverable, with the signature the plan fixes. The scaffold has no
`src/shop/search.py`, so a run that implemented nothing fails here (a regex on
a missing file fails in every match mode).
