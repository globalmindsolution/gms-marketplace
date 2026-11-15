---
type: regex
target: last_message
pattern: '\bno\b[^\n]{0,40}\barchitecture\b|\barchitecture (?:doc(?:ument)?s?|set)\b[^\n]{0,60}\b(?:not found|missing|does(?:n.t| not) exist|absent)'
flags: i
---

The skill's stop is stated, not silent: the reply says there is no
architecture set to audit (the skill's own words are "no architecture set
found").
