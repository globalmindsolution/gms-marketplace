---
type: regex
target: files
pattern: '/steps/create-project/'
match: not_contains
---

Exactly one leg per invocation, and never the greenfield one on a repo with a
build manifest.
