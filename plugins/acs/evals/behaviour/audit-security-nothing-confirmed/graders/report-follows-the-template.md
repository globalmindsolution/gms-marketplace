---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-repository-for-security-weaknesses-e64d/steps/audit-security/iter-1/report.md }
pattern: '^## Scope and coverage[ \t]*\n[\s\S]*^## Summary[ \t]*\n[\s\S]*^## Critical[ \t]*\n[\s\S]*^## High[ \t]*\n[\s\S]*^## Medium[ \t]*\n[\s\S]*^## Low[ \t]*\n[\s\S]*^## Advisory[ \t]*\n[\s\S]*^## Refuted[ \t]*$'
flags: m
---

Nothing confirmed is still a report: written from
templates/audit-security-report.md with every `## ` section in the template's
order, each empty severity saying `_None._`. Dropping the sections it had
nothing for -- or the Refuted section a refuted candidate belongs in -- breaks
the contract the post-hook checks.
