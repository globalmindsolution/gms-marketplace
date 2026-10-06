---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-security-of-the-repository-abb3/steps/audit-security/iter-1/report.md }
pattern: '^## Scope and coverage[ \t]*\n[\s\S]*^## Summary[ \t]*\n[\s\S]*^## Critical[ \t]*\n[\s\S]*^## High[ \t]*\n[\s\S]*^## Medium[ \t]*\n[\s\S]*^## Low[ \t]*\n[\s\S]*^## Advisory[ \t]*\n[\s\S]*^## Refuted[ \t]*$'
flags: m
---

The report is written from templates/audit-security-report.md: every `## `
section the template has, in its order -- the contract the post-hook checks.
A report that leaves out the sections it had nothing for (Advisory, Refuted)
or reorders them breaks it; an empty section says `_None._`. No report at all
fails too: a regex on a missing file fails.
