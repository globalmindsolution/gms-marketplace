---
type: regex
target: { source: file, path: docs/operations/runbooks.md }
pattern: '^(?=[\s\S]*^#{1,3}\s+On-call escalation path)(?=[\s\S]*\b15\s?(?:-\s?)?min)'
flags: mi
---

Tailored to the confirmed on-call fact: an unacknowledged page escalates
after 15 minutes. Only the request says so.
