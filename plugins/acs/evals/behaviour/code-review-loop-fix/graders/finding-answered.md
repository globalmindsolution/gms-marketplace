---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/code/result.json }
pattern: '"id"\s*:\s*"F-1-1"[^{}]*"status"\s*:\s*"fixed"|"status"\s*:\s*"fixed"[^{}]*"id"\s*:\s*"F-1-1"'
---

On iteration 2+ every confirmed finding is answered BY ID in the code step's
`result.json` -- `fixed` or `disputed`, no third option -- and `post-code.py`
persists that document. The scaffold's iteration-1 result has no
`resolutions` at all, so a run that fixed the code without answering F-1-1
(the handle the next review closes it by) fails here.
