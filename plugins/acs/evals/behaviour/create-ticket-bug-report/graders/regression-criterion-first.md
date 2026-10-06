---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"acceptance_criteria"\s*:\s*\[\s*"[^"]*[Rr]egression test'
---

A bug's FIRST acceptance criterion is a regression test that reproduces it —
failing before the fix, passing after — which /acs:create-impl-plan makes the
first test of the first slice.
