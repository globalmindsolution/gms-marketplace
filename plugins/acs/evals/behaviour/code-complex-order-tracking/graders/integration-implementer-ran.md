---
type: file_exists
path: .acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-1/implementer-integration.json
---

What separates `complex` from `standard`: after every partition implementer
returns, the leg spawns ONE integration implementer (`slice="integration"`)
over the seams between partitions, and it writes
`iter-<n>/implementer-integration.json`. On this path it runs whenever more
than one partition ran, seams reported or not -- and this plan has two
partitions and names the seam. A run that behaved like `standard` and skipped
it fails here.
