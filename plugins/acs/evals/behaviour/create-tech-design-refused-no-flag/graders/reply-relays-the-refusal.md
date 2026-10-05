---
type: regex
target: last_message
pattern: 'needs_design|not (?:flagged|marked)[^\n]*design|design-significant'
flags: i
---

The refusal is surfaced to the user: the ticket is not flagged needs_design.
