---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/iter-*/gate.json
---

Stage 3 runs only when stage 2 leaves nothing blocking, and on a clean
changeset it must: build, lint, the full unit suite and coverage, recorded in
`iter-<n>/gate.json`. It is the only place the full suite runs in the
pipeline, and there is no zero-findings verdict without it.
