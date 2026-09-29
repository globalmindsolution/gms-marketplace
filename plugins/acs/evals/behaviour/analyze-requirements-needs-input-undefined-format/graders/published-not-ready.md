---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/analysis.md }
pattern: '^---\n(?:[a-z_]+:[^\n]*\n)*ready_for_planning:[ \t]*false[ \t]*\n(?:[a-z_]+:[^\n]*\n)*---'
---

A not-ready analysis is still published -- "the artifact the answers come back
to" -- and its machine-read front matter says `ready_for_planning: false`. A
guessed format published as ready, or nothing published, fails.
