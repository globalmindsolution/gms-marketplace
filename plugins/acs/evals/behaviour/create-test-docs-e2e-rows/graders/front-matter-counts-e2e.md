---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/test-cases.md }
pattern: '^-{3}\n(?=(?:[a-z0-9_]+:[^\n]*\n)*cases:[ \t]*[1-9]\d*[ \t]*\n)(?=(?:[a-z0-9_]+:[^\n]*\n)*e2e_cases:[ \t]*[1-9]\d*[ \t]*\n)'
---

`e2e_cases` is what the create-e2e-tests gate trusts over the table: it must
be a positive integer here. 0 would shut the gate on a ticket that owes e2e.
