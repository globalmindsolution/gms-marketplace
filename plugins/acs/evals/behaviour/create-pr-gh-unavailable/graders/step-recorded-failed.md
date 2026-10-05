---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"status"\s*:\s*"failed"'
---

The skill ran its Finish on the failure path: it wrote a result document with
status `failed` and ran `post-create-pr.py`, which is what writes this file.
A run that stopped without finishing leaves no state file (the grader fails on
a missing file), and a run that faked success records `completed`.
