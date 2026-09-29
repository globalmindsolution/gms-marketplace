---
type: regex
target: { source: file, path: src/shop/auth.py }
pattern: 'compare_digest'
---

AC-3 and the plan's first risk: digests are compared with
`hmac.compare_digest`, never `==`. The scaffold has no `src/shop/auth.py`, so a
run that implemented nothing fails here too.
