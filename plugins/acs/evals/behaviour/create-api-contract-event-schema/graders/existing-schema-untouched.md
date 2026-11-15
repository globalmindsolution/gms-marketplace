---
type: regex
target: { source: file, path: schemas/events/order.created.json }
pattern: '"title": "order\.created",\n  "type": "object",\n  "required": \["event", "event_id", "occurred_at", "schema_version", "payload"\],'
---

The existing machine-readable contract is evidence of today's shape, read and
never edited: order.created.json keeps its title and envelope exactly as the
scaffold wrote them.
