---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: 'test-runs/run-[^/"\\]+/results\.json'
---

The minted ticket's description links the results artifact, as step 4b
requires -- so the ticket and the artifact describe the same run.
