---
type: regex
target: { source: file, path: docs/architecture/lld/flows/list-orders.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*sequenceDiagram)(?=[\s\S]*/orders)'
---

The confirmed new flow gets its own file under the name the request fixed,
as a Mermaid sequence diagram of GET /orders.
