---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/api-contract.md }
pattern: '^### [^\n]*\b(?:GET|POST|PUT|PATCH|DELETE) /'
flags: m
match: not_contains
---

The ticket adds no endpoint. An item shaped as an HTTP route (a webhook POST,
an events endpoint) invents a surface the plan does not declare.
