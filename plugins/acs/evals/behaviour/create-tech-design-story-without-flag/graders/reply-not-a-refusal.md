---
type: regex
target: last_message
pattern: 'not (?:flagged|marked)[^\n]*design|needs_design|design-significant'
flags: i
match: not_contains
---

The reply reports the published design; it never relays the retired refusal
("not flagged needs_design", "only runs for design-significant tickets").
