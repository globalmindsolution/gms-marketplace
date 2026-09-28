---
type: regex
target: files
pattern: '/EVAL-\d+/|/steps/'
match: not_contains
---

Exit 2 stops the umbrella before dispatch: no delivery ticket partition and
no leg step exist.
