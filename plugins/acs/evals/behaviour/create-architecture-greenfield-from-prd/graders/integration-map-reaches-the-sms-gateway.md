---
type: regex
target: { source: file, path: docs/architecture/hld/integration-map.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*flowchart)(?=[\s\S]*booking-api)(?=[\s\S]*reminder-worker)(?=[\s\S]*SMS)'
---

The API landscape is a Mermaid `flowchart` in the container vocabulary the
HLD pins: booking-api exposes the booking JSON API, and reminder-worker
consumes the external SMS gateway's API. A landscape of one invented app, or
one that drops the gateway, is not the confirmed design.
