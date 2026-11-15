---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"severity"\s*:\s*"high"'
---

The bug's `severity` is its own field (`critical|high|medium|low`), separate
from `priority`: the request gives severity high and priority medium.
