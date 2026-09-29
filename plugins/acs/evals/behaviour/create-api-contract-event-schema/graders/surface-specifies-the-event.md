---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/api-contract.md }
pattern: '^## Surface[ \t]*$(?:(?!^## )[\s\S])*^### [^\n]*order\.shipped(?:(?!^## )[\s\S])*event_id'
flags: m
---

The surface is a message, and the skill covers "every endpoint, command or
message": a `### ` item for order.shipped that specifies its envelope's
`event_id` (AC-2, and the dedup key AC-3 relies on).
