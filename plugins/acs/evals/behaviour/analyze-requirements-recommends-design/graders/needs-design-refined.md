---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/requirements-refined.json }
pattern: '"needs_design"\s*:\s*true'
---

The confirmed flag goes through `acs.py requirements refine` (ADR-0128): the
run's refined requirements -- what every later skill reads through
`context.requirements` -- carry `needs_design: true`. A run that patched only
the ticket (`acs.py ticket save`) or hand-edited ticket.json leaves the run's
requirements saying no design is needed.
