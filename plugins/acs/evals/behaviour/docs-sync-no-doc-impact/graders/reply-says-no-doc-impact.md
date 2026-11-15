---
type: regex
target: last_message
pattern: 'no (?:docs?|documentation)\b[^\n]*(?:change|update|impact|stale|drift|commit)|nothing (?:to|needed) (?:update|commit|sync|change)|no doc files? (?:were |was )?(?:committed|changed)|docs committed[^\n]*none|doc files (?:committed|written)[^\n]*(?:none|\b0\b)'
flags: i
---

The report says no doc needed updating (the completion block's Results line,
or its summary), rather than listing a commit.
