---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan/state.json }
pattern: '"status"\s*:\s*"interrupted"[\s\S]*"status"\s*:\s*"completed"'
---

The handed-off invocation stays on the record; the resumed run appends one
the post-hook finalized `completed`.
