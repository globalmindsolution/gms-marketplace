---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/clarifications.json }
pattern: '"status"\s*:\s*"open"'
---

"Record every outgoing question as `open` (`clarify.py add` without
`--answer`)." The format question has no answer and no safe default, so it
must not be recorded answered or as an assumption.
