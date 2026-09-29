---
type: regex
target: files
pattern: '^schemas/events/[^/\n]*shipped[^/\n]*\.json$'
flags: m
---

The repo keeps machine-readable contracts -- one JSON Schema per event in
schemas/events/ -- so the mode is that directory, and the run updates it "in
the format they already use": a new schema for order.shipped beside
order.created.json.
