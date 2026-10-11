---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/plan-a-roadmap-with-no-prd-ddd9/steps/manage-roadmap/state.json }
pattern: '"status"\s*:\s*"failed"'
---

The refusal is a terminal outcome, so the mandatory Finish still ran: the
result document went through the post-hook, which recorded the step `failed`
and released the lock. A run that just stopped leaves no state here.
