---
type: regex
target: last_message
pattern: '(?:comment|bump|append|updat)[^\n]*EVAL-1\b|EVAL-1\b[^\n]*(?:comment|bump|append|updat)'
flags: i
---

The report's tickets line says the existing ticket was bumped, by id --
not that one was minted.
