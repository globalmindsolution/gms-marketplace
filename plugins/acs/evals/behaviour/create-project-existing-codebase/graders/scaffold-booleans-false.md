---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-project/result.json }
pattern: '"build"\s*:\s*true|"lint"\s*:\s*true|"tests"\s*:\s*true|"coverage_tooling"\s*:\s*true'
match: not_contains
---

On the refusal "all `states.scaffold` booleans `false`": nothing was built,
linted or tested.
