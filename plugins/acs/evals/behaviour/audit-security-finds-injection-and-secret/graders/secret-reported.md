---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-security-of-the-repository-abb3/steps/audit-security/iter-1/report.md }
pattern: '## (?:Critical|High|Medium|Low)[ \t]*\n(?:(?!\n## )[\s\S])*?config/production\.ini'
---

The hard-coded payments token in config/production.ini is a confirmed
finding at a severity (a credential in the tree is reported as live until
someone says it has been rotated), not left out, advisory or refuted.
