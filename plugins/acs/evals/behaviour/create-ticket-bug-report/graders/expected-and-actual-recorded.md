---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"expected"\s*:\s*"[^"]+"[\s\S]*"actual"\s*:\s*"[^"]+"|"actual"\s*:\s*"[^"]+"[\s\S]*"expected"\s*:\s*"[^"]+"'
---

Both `expected` and `actual` are recorded, each non-empty.
