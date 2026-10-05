---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/**
exists: false
---

The pre-hook refuses the Skill call, so the skill never reaches its `acs step
start` and no create-pr step exists. `acs step start` re-applies the review
brake and refuses too, so a step here means the kernel let it through, or the
run wrote a result document as if the PR had been attempted.
