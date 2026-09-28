---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/test-cases.md }
pattern: '^---\n(?=(?:[a-z0-9_]+:[^\n]*\n)*cases:[ \t]*[1-9]\d*[ \t]*\n)(?=(?:[a-z0-9_]+:[^\n]*\n)*e2e_cases:[ \t]*\d+[ \t]*\n)'
---

`cases` and `e2e_cases` are integers in the front matter: the
`/acs:create-e2e-tests` gate trusts `e2e_cases` over the table when it is an
integer, so a missing or non-integer value is the one defect downstream cannot
catch.
