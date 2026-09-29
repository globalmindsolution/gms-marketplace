---
type: regex
target: { source: file, path: docs/architecture/lld/flows/list-customers.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*sequenceDiagram)(?=[\s\S]*/customers)'
---

Every diagram is Mermaid and a flow file is a `sequenceDiagram`; this one
must also be the flow the code actually serves (GET /customers), not a
generic placeholder.
