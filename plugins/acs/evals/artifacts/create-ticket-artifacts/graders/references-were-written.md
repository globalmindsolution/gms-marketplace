---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"references"\s*:\s*\[[\s\S]*"path"\s*:\s*"docs/product/prd\.md'
---

The minted ticket stores its `references` (ADR-0140): materialization runs
`acs.py ticket references --ticket EVAL-1 --write`, which lists what the
standard layout holds for the ticket -- here at least the PRD, which even a
ticket with no feature falls back to. The placeholder `--allocate` writes has
no `references` key, so a run that skipped the step fails here.
