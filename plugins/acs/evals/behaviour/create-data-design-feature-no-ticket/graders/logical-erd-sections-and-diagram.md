---
type: regex
target: { source: file, path: docs/architecture/lld/orders/data/logical-erd.md }
pattern: '^## Scope[ \t]*$[\s\S]*^## Entities[ \t]*$[\s\S]*^## Relationships[ \t]*$[\s\S]*^## Diagram[ \t]*$(?:(?!^## )[\s\S])*^```mermaid[ \t]*\n[ \t]*erDiagram\b(?:(?!^```)[\s\S])*\bORDER_LINES?\b'
flags: m
---

The logical ERD's required sections in order -- Scope, Entities,
Relationships, Diagram -- with a Mermaid `erDiagram` that details the HLD's
conceptual ORDER_LINE.
