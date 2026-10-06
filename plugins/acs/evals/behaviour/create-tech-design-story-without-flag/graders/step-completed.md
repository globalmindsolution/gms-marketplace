---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-tech-design/state.json }
pattern: '"status":\s*"completed"'
---

The gate admitted the story and the mandatory Finish ran: `acs step start`
opened the step (it repeats the subject check, so a refusal there leaves no
state.json) and `post-create-tech-design.py` recorded it `completed`.
