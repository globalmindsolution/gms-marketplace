---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/code/state.json }
pattern: '"status"\s*:\s*"completed"'
---

The step machine advanced `code` to completed. A step's state file holds its
invocations (ADR-0097), and the run id for a ticket subject is the ticket id.
Coarser than the original's "LAST invocation is completed": on a fresh ticket
code runs once, so presence and last-ness coincide, but a retried run could
pass here on an earlier invocation.
