---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"needs_design"\s*:\s*true'
---

The user confirmed the recommendation up front, so the skill applies it
through `acs.py requirements refine` with `{"needs_design": true}`, which
records it in the run's requirements AND patches and re-indexes the ticket
(ADR-0128). Recommending without applying leaves the ticket
routed straight to planning with no design.
