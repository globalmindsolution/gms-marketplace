---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/merge-pr/**
exists: false
---

The pre-hook refuses the Skill call, so the skill never reaches `acs step
start` and no merge-pr step exists. `acs step start` re-checks the PR
reference and refuses too, so one here means the kernel let the step through,
or the run recorded a merge outcome by hand.
