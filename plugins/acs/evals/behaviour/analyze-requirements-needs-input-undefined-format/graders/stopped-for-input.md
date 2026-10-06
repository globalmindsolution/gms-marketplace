---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"analyze-requirements"\s*:\s*\{[^{}]*"status"\s*:\s*"interrupted"[^{}]*"stop_reason"\s*:\s*"needs_input"'
---

The needs_input arm finishes through the post-hook as an interrupted step
whose `stop_reason` is `needs_input` -- the kernel's spelling of "stopped for
user input" (a result `status: needs_input` is refused by the post-hook). A
`completed` step would open planning on an unplannable ticket.
