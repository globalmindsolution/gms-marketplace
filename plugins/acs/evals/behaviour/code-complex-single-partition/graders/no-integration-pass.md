---
type: regex
target: files
pattern: 'steps/code/iter-\d+/implementer-integration\.json'
match: not_contains
---

What separates `complex` from `standard` is the integration implementer over
the seams between partitions -- and a plan with a single partition has none,
so the leg skips it. A run that spawned it anyway fails here.
