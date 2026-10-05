---
type: regex
target: files
pattern: 'example-shop/EVAL-\d+/ticket\.json'
match: not_contains
---

No skill requires a ticket (ADR-0128), and the user asked for none: a run
that detoured through /acs:create-ticket, or minted one to have somewhere to
publish, fails here.
