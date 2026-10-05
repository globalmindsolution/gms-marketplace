---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/plan.md }
pattern: '^## Contract[ \t]*$(?:(?!^## )[\s\S])*^[ \t]+api_contract:'
flags: m
match: not_contains
---

`owes` names the steps the plan settles: test cases and e2e. The API
contract is no longer one of them (ADR-0134) -- /acs:create-api-contract is a
Design skill that ran before this plan, and its contract is an input. A
Contract block that still owes `api_contract` writes a key nothing reads. (A
regex on a missing file fails, so this also fails a run that published
nothing.)
