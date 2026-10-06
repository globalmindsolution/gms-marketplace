---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"children"\s*:\s*\[\s*\]'
---

An epic's own creation run always ends with `children: []`: fan-out is
deferred to `/acs:create-ticket EVAL-1 --fan-out` after `/acs:create-tech-design`.
