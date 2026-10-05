---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-1/implementer.json
---

One partition, one implementer: spawned alone, it carries no `slice` and
reports at `iter-<n>/implementer.json`. A run that split the single task
across sliced implementers writes `implementer-<k>.json` instead and fails
here.
