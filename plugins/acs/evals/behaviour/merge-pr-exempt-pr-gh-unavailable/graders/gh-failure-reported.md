---
type: regex
target: last_message
pattern: '\bgh\b|GitHub CLI'
flags: i
---

The reply surfaces `acs step start`'s refusal verbatim: gh is required for
`--pr` mode and could not read the PR (not on PATH, or no GitHub remote). A
run that stopped silently, or reported a merge, names neither.
