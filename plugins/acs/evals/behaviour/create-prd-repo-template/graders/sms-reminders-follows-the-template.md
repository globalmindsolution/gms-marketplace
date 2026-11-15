---
type: regex
target: { source: file, path: docs/product/features/sms-reminders/prd.md }
pattern: '^(?=[\s\S]*^##\s+Summary\s*\n[\s\S]*^##\s+Goals served\s*\n[\s\S]*^##\s+Requirements\s*\n[\s\S]*\*\*R1\*\*[\s\S]*^##\s+Acceptance criteria\s*\n[\s\S]*^##\s+Dependencies\s*\n[\s\S]*^##\s+Rollout\s*\n(?:(?!^## )[\s\S])*?(?:beta|flag)[\s\S]*^##\s+Out of scope\s*$)'
flags: mi
---

The repo's own feature template replaces the built-in (ADR-0147): `sms-reminders`'s
PRD carries its seven sections in order -- `## Rollout` between Dependencies
and Out of scope, filled from the stated plan (a beta group, or a feature
flag) -- not the built-in six.
