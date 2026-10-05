---
type: regex
target: last_message
pattern: '(?i)\bkept\b[^\n]{0,40}\blocal\b'
---

The completion report names where the analysis went -- "kept local (team
default)" -- so a reader who expected a docs/ file knows why there is none.
