---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"status"\s*:\s*"failed"'
---

The skill ran its Finish on the failure path -- uncommitted work it may not
ship (a "needs user input" failure in a run nobody can answer), or the
critical base detection gh cannot answer, whichever it met first: a result
document with status `failed`, then `post-create-pr.py`, which writes this
file. A run that never finished leaves no file; one that faked success
records `completed`.
