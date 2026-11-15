---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/plan.md }
pattern: '^## Contract[ \t]*$(?=(?:(?!^## )[\s\S])*^owes:[ \t]*$)(?=(?:(?!^## )[\s\S])*^[ \t]+test_cases:[ \t]*(?:true|false)[ \t]*$)(?=(?:(?!^## )[\s\S])*^[ \t]+reason:[ \t]*\S)(?!(?:(?!^## )[\s\S])*^[ \t]+api_contract:)'
flags: m
---

The Contract block's `owes` table is explicit -- "silence is not permission
to skip" -- with the steps the plan settles (`test_cases`, `e2e`) and a
checkable `reason`. It carries no `api_contract` key: an operator log line
changes no interface, and the API contract is a Design document now
(ADR-0134), never a step a plan owes. A missing `owes` table, a missing
reason, or the retired key fails.
