---
type: regex
target: { source: file, path: docs/requirements/functional/appointment-reminders.md }
pattern: '^(?=DRAFT\s*[—–-]+\s*human-confirm-required)(?=[\s\S]*\bMUST\b)(?=[\s\S]*0?9:00)(?=[\s\S]*18:00)'
flags: mi
---

The second functional file, DRAFT-marked, with the one elicited fact the PRD
does not carry: the 09:00-18:00 sending window.
