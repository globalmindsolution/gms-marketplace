---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/plan.md }
pattern: '^## Contract[ \t]*$(?:(?!^## )[\s\S])*^[ \t]+api_contract:[ \t]*false[ \t]*$(?:(?!^## )[\s\S])*^[ \t]+reason:[ \t]*\S'
flags: m
---

The analysis declares `api_surface: false` and the change is an operator log
line, so the plan owes no API contract -- and says why in `reason`. That
`false` is what lets the create-api-contract pre-hook settle the step as an
evidenced `no_surface_owed` instead of spawning a contract run. `true`, or no
`owes` entry at all ("silence is not permission to skip"), fails.
