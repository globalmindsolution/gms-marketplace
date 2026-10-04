---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/plan.md }
pattern: '^## Contract[ \t]*$(?:(?!^## )[\s\S])*^[ \t]+api_contract:[ \t]*true[ \t]*$'
flags: m
---

The published analysis declares `api_surface: true` and the ticket adds a
query parameter, a response field and an error code to GET /customers, so the
plan must owe an API contract. `false` makes the create-api-contract pre-hook
complete that step as `no_surface_owed` with no contract written.
