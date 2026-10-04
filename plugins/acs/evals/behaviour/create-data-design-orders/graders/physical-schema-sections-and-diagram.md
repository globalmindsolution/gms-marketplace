---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/physical-schema.md }
pattern: '^## Scope[ \t]*$[\s\S]*^## Tables[ \t]*$[\s\S]*^## Indexes and constraints[ \t]*$[\s\S]*^## Diagram[ \t]*$(?:(?!^## )[\s\S])*^```mermaid[ \t]*\n[ \t]*erDiagram\b[\s\S]*^## Migration outline[ \t]*$'
flags: m
---

The physical schema's required sections in order -- Scope, Tables, Indexes
and constraints, Diagram (a Mermaid `erDiagram`), Migration outline.
