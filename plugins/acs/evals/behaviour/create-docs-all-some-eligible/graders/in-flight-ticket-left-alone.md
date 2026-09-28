---
type: file_exists
path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-docs/result.json
exists: false
---

The operations set is in flight on EVAL-1 (handed off). An `all` run excludes
it from the batch -- it is resumed only by its own ticket id -- so this run
never finalizes EVAL-1's create-docs step.
