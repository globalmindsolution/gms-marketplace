---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-4/ticket.json }
pattern: '"acceptance_criteria": \[\s*"[^"]*email'
---

new-ticket.py has no `--acceptance-criteria` flag, so the fan-out writes each
confirmed child's criteria into its own ticket afterwards (`acs.py ticket
save`). The last child, "Status-change emails", must carry its confirmed
criterion rather than an empty list.
