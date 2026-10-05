---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-tech-design/state.json }
pattern: '"status":\s*"completed"'
---

The mandatory Finish ran: result.json written and `post-create-tech-design.py`
accepted it, which records the invocation `completed` -- the `/acs:code` gate
stays closed until it does. `acs step start` alone leaves it `in_progress`;
a `handed_off` stop that asked instead of deciding records that status
instead.
