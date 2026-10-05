---
type: regex
target: { source: file, path: docs/architecture/lld/order-tracking/api/order-events.md }
pattern: '^## Surface[ \t]*$(?:(?!^## )[\s\S])*^### [^\n]*order\.shipped(?:(?!^## )[\s\S])*event_id'
flags: m
---

`## Surface` carries a `### ` item for the new event beside order.created,
and its envelope names `event_id` -- the key consumers deduplicate on (AC-3).
