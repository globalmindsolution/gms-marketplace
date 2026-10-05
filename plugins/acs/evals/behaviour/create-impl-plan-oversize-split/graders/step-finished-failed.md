---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-impl-plan"\s*:\s*\{[^{}]*"status"\s*:\s*"failed"'
---

"On split: the run ends in an orderly way": the Finish steps run with
`status: "failed"` and a summary saying the user chose to split, so the
post-hook closes the step. A `completed` step would open `/acs:code` on a
plan the user rejected; an `in_progress` one skipped Finish.
