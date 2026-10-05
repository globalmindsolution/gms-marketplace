---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-test-docs"\s*:\s*\{[^{}]*"status"\s*:\s*"interrupted"[^{}]*"stop_reason"\s*:\s*"needs_input"'
---

`untraced_acs` must be `[]` on a completed run, so this one stops for input:
the post-hook records an interrupted step with `stop_reason: needs_input`
(the kernel's spelling; a result `status: needs_input` is refused).
