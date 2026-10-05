---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-2/ticket.json }
pattern: '^\s*"parent": "EVAL-1",?$'
flags: m
---

Each child records the epic as its `parent` -- the epic carries the design,
and children inherit it. The child lives in the workspace partition's
`ticket.json`: since ADR-0128 no ticket file is written into the repo.
