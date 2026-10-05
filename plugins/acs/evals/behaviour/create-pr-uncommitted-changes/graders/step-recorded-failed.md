---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"status"\s*:\s*"failed"'
---

The skill ran its Finish on the failure path: after the commit phase, the
critical base detection gh cannot answer stops the run before the push -- a
result document with status `failed`, then `post-create-pr.py`, which writes
this file. A run that never finished leaves no file; one that faked success
records `completed`.
