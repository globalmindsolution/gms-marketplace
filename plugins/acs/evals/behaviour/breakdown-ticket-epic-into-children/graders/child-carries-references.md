---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-3/ticket.json }
pattern: '"references"\s*:\s*\[[\s\S]*"path"\s*:\s*"docs/architecture/lld/order-tracking/EVAL-1/tech-design\.md"'
---

Each child records its references (ADR-0140): the breakdown runs `acs.py
ticket references --ticket <child> --write` once per child, and the standard
layout finds the PARENT epic's design records from the child's `parent` -- so
the child's list names the epic's approved tech design without anyone passing
it. new-ticket.py writes no `references` key, so a breakdown that skipped the
step fails here.
