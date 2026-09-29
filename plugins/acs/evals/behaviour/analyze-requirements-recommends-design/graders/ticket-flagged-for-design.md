---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"needs_design"\s*:\s*true'
---

The user confirmed the recommendation up front, so the skill applies it
through the CLI that re-indexes the ticket (`acs.py ticket save` with
`{"needs_design": true}`). Recommending without applying leaves the ticket
routed straight to planning with no design.
