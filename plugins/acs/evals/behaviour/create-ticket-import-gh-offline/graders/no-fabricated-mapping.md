---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"external"\s*:\s*null'
---

The `external` mapping is recorded only from a successful pull. A run that
wrote `{"provider": "github", "key": "123"}` without reading the issue faked
the link.
