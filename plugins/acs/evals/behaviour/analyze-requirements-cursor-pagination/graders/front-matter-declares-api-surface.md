---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/analysis.md }
pattern: '^-{3}\n(?:[a-z_]+:[^\n]*\n)*api_surface:[ \t]*true[ \t]*\n(?:[a-z_]+:[^\n]*\n)*-{3}'
---

`api_surface` is read by machines: ship.yaml's `api_surface_changed`
predicate and the `/acs:create-api-contract` gate. The ticket adds a query
parameter, a response field and an error code to a documented public endpoint
(README.md's API section), so the front matter must say `true`. A missing,
`false`, or out-of-front-matter value fails.
