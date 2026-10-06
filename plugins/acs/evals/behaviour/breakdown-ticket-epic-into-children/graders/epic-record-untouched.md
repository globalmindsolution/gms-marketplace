---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"title"\s*:\s*"Order tracking"[\s\S]*"type"\s*:\s*"epic"'
---

Breaking down an epic never re-analyzes or rewrites its own record: only its
`children` change.
