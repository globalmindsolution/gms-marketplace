---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-repository-for-security-weaknesses-e64d/steps/audit-security/iter-1/report.md }
pattern: '## (?:Critical|High|Medium|Low)[ \t]*\n(?:(?!\n## )[\s\S])*?stats\.py'
match: not_contains
---

The f-string queries in src/shop/stats.py interpolate only `TABLE`, a module
constant; the one caller-supplied value is a bound parameter. If an auditor
raises them, the adjudicator refutes them, and a refuted candidate goes under
`## Refuted` with its reason -- never under Critical, High, Medium or Low.
(Not raising them at all also passes; a missing report fails.)
