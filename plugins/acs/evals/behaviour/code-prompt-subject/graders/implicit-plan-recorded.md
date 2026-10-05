---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/*/steps/code/plan.md
---

With no plan on disk, /acs:code derives an implicit plan from the subject and
records it at `steps/code/plan.md` of the prompt's own run (the run id is a
slug of the prompt, so the glob does not name it). A run that implemented
without writing the plan down leaves the path judgement with nothing to
check against.
