---
type: file_exists
path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/iter-*/commit-plan.json
---

The confirmed plan is on disk before anything is committed (SKILL.md step C3):
it is what `acs.py pr commit --plan` executes and what a resumed run finishes
instead of asking again. A run that committed without planning, or refused to
commit at all, writes none.
