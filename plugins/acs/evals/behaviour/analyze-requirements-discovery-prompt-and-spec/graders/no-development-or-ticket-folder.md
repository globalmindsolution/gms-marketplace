---
type: regex
target: files
pattern: '^docs/(?:development|tickets)/'
flags: m
match: not_contains
---

A Discovery analysis is the feature's, at the feature root -- not a delivery
run's (`docs/development/<feature>/<run-id>/`) and never the retired ticket
docs tree.
