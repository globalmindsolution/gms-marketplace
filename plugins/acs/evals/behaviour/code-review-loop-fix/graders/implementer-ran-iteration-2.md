---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-2/implementer*.json
---

The fix went through an implementer on the loop's own iteration: its report
lands under `steps/code/iter-2/`. The scaffold wrote only `iter-1/`, so a run
that stayed on iteration 1, or fixed the code without the leg's implementer,
fails here.
