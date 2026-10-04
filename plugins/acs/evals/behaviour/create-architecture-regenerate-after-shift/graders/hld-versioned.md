---
type: regex
target: { source: file, path: docs/architecture/hld/c4-container.md }
pattern: '^-{3}\nstatus: "?(?:implemented|proposed)"?\nversion: [1-9]\d*\ntickets:(?:\n  - "?EVAL-1"?| \[[^\]\n]*EVAL-1)'
---

ADR-0122: every HLD file carries version front matter, set only through
`acs.py design`. The scaffold's set predates it, so the regenerated container
view gets its first block (`design init`; `implemented` -- it documents the
code as built -- or `proposed` if the run then bumps it as a change), and the
delivery ticket is recorded in `tickets`. A regenerated file with no block
fails here.
