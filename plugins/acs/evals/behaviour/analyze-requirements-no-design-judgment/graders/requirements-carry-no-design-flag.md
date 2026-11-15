---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/requirements.md }
pattern: 'needs_design'
match: not_contains
---

`acs.py requirements refine` takes no design key (ADR-0139), so the run's
requirements every later skill reads say nothing about design.
