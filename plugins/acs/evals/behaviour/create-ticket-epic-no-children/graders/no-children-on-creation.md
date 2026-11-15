---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"children"\s*:\s*\[\s*\]'
---

An epic's own creation run always ends with `children: []`: the breakdown is
deferred to `/acs:breakdown-ticket EVAL-1`.
