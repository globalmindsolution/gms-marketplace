---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/code/state.json }
pattern: '"started_at"'
match: count:1
---

The implementation is recorded and committed; re-running /acs:code (a second
invocation here) is redoing a completed step the cursor had moved past.
