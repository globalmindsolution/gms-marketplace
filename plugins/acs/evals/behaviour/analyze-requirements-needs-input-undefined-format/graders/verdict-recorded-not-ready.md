---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/state.json }
pattern: '"ready_for_planning"\s*:\s*false'
---

`states.ready_for_planning: false` is the verdict `/acs:create-impl-plan`
consumes; it must match the published front matter.
