---
type: regex
target: { source: file, path: docs/architecture/hld/c4-container.md }
pattern: '^-{3}\nstatus: "?proposed"?\nversion: [1-9]\d*\ntickets:'
---

ADR-0122: every HLD file opens with version front matter, set only through
`acs.py design init`. Greenfield, nothing is built, so the design is ahead of
the code: `status: proposed`. The run is ticketless (ADR-0127), so `tickets`
names no delivery ticket. The team's approval of the docs PR `/acs:create-pr`
opens makes it `approved` later, and `/acs:docs-sync` makes it `implemented`
once the code lands. A file with no block, or one claiming `implemented` for
containers that do not exist yet, fails here.
