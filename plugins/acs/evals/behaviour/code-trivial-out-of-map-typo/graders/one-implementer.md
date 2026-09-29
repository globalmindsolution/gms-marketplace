---
type: regex
target: files
pattern: 'steps/code/iter-\d+/implementer-'
match: not_contains
---

The trivial path's defining machinery: exactly one implementer, never sliced,
so no `implementer-<k>.json` exists. On its own this passes a run that did
nothing; the other graders catch that.
