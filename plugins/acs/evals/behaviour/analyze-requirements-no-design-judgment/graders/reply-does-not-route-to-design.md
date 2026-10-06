---
type: regex
target: last_message
pattern: 'create-tech-design'
match: not_contains
---

The completion report's Next is `/acs:create-impl-plan EVAL-1` (and
`/acs:create-api-contract` when an interface changes); it no longer suggests
a tech design.
