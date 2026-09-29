---
type: regex
target: last_message
pattern: '\b\d\s*(?:/|of)\s*3\b|\b3 suites'
flags: i
match: not_contains
---

Nothing in the report counts three suites: the unselected ones were not run.
