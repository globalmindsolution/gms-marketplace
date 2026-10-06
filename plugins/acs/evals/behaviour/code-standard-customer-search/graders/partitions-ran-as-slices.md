---
type: file_exists
path: .acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-1/implementer-2.json
---

The standard path's defining machinery: one implementer per disjoint file-map
partition, spawned in parallel from iteration 1, each writing its own
`iter-<n>/implementer-<k>.json` where `k` is the plan task number. The plan has
two disjoint tasks, so task 2's slice report exists. A run that folded both
tasks into one un-sliced implementer writes `implementer.json` and fails here.
