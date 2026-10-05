---
type: file_exists
path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-1/implementer-2.json
---

Docs-only relaxes TDD, not the path's machinery: two disjoint partitions still
run as two slices, each writing `iter-<n>/implementer-<k>.json`. A run that
folded both into one un-sliced implementer fails here.
