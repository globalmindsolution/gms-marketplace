---
type: regex
target: { source: file, path: docs/architecture/hld/c4-container.md }
pattern: '^-{3}\nstatus: "?(?:implemented|proposed)"?\nversion: [1-9]\d*\ntickets:'
---

ADR-0122: every HLD file carries version front matter, set only through
`acs.py design`. The scaffold's set predates it, so the regenerated container
view gets its first block (`design init`; `implemented` -- it documents the
code as built -- or `proposed` if the run then bumps it as a change). The run
is ticketless (ADR-0127), so `tickets` names no delivery ticket. A regenerated
file with no block fails here.
