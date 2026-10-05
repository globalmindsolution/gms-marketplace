---
type: file_exists
path: '.git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-tech-design/**'
exists: false
---

A refused invocation opens no step. `acs step start --step create-tech-design`
repeats the subject check and refuses too, so a state.json here means the
kernel let a refused design through.
