---
type: regex
target: { source: file, path: docs/architecture/lld/order-tracking/api/order-events.md }
pattern: '^### [^\n]*\b(?:GET|POST|PUT|PATCH|DELETE) /'
flags: m
match: not_contains
---

The ticket adds no endpoint. An item shaped as an HTTP route (a webhook POST,
an events endpoint) invents a surface the requirements do not ask for. (A
regex on a missing file fails, so this also fails a run that deleted the
document.)
