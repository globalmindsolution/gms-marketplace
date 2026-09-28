---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-design/state.json }
pattern: '"status":\s*"completed"'
---

The mandatory Finish ran: result.json written and `post-create-design.py`
accepted it, which records the invocation `completed` -- the `/acs:code` gate
stays closed until it does. `acs step start` alone leaves it `in_progress`;
a `handed_off` stop that asked instead of deciding records that status
instead.
