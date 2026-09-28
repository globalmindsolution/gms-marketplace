---
type: regex
target: files
pattern: '^docs/(?:quality|operations|principles)/'
flags: m
match: not_contains
---

No file under an ineligible set's location is created: quality and
principles already ship, and operations belongs to EVAL-1.
