---
type: regex
target: files
pattern: 'steps/code/iter-\d+/implementer-'
match: not_contains
---

The trivial path's defining machinery: exactly one implementer, never sliced,
so its report is `iter-<n>/implementer.json` and no `implementer-<k>.json`
exists. A sliced report means the run behaved like a deeper path. On its own
this passes a run that did nothing; the other graders catch that.
