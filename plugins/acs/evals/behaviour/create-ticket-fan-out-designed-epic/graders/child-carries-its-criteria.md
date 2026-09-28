---
type: regex
target: { source: file, path: docs/tickets/EVAL-4/ticket.md }
pattern: '^## Acceptance criteria\n\n1\. [^\n]*email'
flags: m
---

new-ticket.py has no `--acceptance-criteria` flag, so the fan-out writes each
confirmed child's criteria into its own ticket afterwards (`acs.py ticket
save`). The last child, "Status-change emails", must carry its confirmed
criterion rather than an empty list.
