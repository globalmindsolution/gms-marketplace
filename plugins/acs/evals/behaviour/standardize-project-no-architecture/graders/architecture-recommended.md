---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json }
pattern: '"recommended_follow_ups"\s*:\s*\[[^\]]*create-architecture'
---

With no architecture set, "run `/acs:create-architecture`" reaches the user
only as a `recommended_follow_ups` entry. A run that stopped at Start never
writes a result document; one that forgot the set records no such entry.
