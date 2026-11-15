---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/analysis/README.md }
pattern: '^## Cross-cutting risks and decisions[ \t]*$(?:(?!^## )[\s\S])*/customers'
flags: m
---

The ticket adds a query parameter, a response field and an error code to a
documented public endpoint (README.md's API section), so the README names GET
/customers as an interface the change alters -- what points the change to
/acs:create-api-contract, the Design skill that designs it (ADR-0134).
