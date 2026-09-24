---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/tickets-index.json }
pattern: '"EVAL-1"'
---

The first ticket minted under prefix EVAL is EVAL-1, and the repo-level index
must carry it. `example-shop` is the partition id acs derives from the fixture's
git remote, so the path is deterministic.
