---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/plan.md }
pattern: 'api/customers\.md|EVAL-1/api-contract\.md'
---

The approved API contract is an input to the plan (ADR-0134): the run record
`artifacts show` reports and the interface document it links are binding, so
the plan names the contract it implements. A plan that never cites it was
planned from the analysis alone.
