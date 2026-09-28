---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan/state.json }
pattern: '"status":\s*"completed"'
---

The mandatory Finish ran: result.json written and `post-create-impl-plan.py`
accepted it. `acs step start` alone leaves the invocation `in_progress`.
