---
type: file_exists
path: '.acs/state-machine/example-shop/runs/EVAL-1/steps/create-design/**'
exists: false
---

A refused invocation opens no step. `acs step start --step create-design`
repeats the subject check and refuses too, so a state.json here means the
kernel let a refused design through.
