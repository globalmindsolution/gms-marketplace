---
type: regex
target: last_message
pattern: '\b1\s*(?:/|of)\s*1\b[^\n]*pass|\b1 (?:suite )?(?:run|ran)\b[^\n]*\bpass'
flags: i
---

The pass count is against the suites RUN: one of one. A run that ran all
three reports 1/3.
