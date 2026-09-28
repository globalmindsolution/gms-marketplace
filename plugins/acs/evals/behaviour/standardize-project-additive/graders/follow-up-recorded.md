---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json }
pattern: '"recommended_follow_ups"\s*:\s*\[[\s\S]*principles'
---

The missing principles set surfaces as a `recommended_follow_ups` entry in
the leg's result document (at the top level as SKILL.md writes it, or under
`states`, where the result schema admits it). A run that never reached Finish
has no result.json.
