---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-4/ticket.json }
pattern: '"acceptance_criteria": \[\s*"[^"]*export'
---

new-ticket.py has no `--acceptance-criteria` flag, so the breakdown writes each
confirmed child's criteria into its ticket afterwards (`acs.py ticket save`):
the export task carries its own.
