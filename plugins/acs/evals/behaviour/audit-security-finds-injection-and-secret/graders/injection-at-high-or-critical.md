---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-security-of-the-repository-abb3/steps/audit-security/iter-1/report.md }
pattern: '## (?:Critical|High)[ \t]*\n(?:(?!\n## )[\s\S])*?(?:CWE-89(?:(?!\n## )[\s\S])*orders_api\.py|orders_api\.py(?:(?!\n## )[\s\S])*CWE-89)'
---

The injection is confirmed and ranked by its reach: GET /orders/search takes
`q` from the query string into an f-string that cursor.execute runs unbound,
on a route with no login -- any caller reads every order. It appears under
`## Critical` or `## High` with CWE-89 and src/shop/orders_api.py; under
Medium, Low, Advisory or Refuted it fails.
