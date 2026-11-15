---
type: regex
target: { source: file, path: docs/architecture/lld/orders/components/orders.md }
pattern: '^## Responsibility[ \t]*$[\s\S]*^## Internals[ \t]*$(?:(?!^## )[\s\S])*^```mermaid[ \t]*\n[ \t]*flowchart\b[\s\S]*^## Types[ \t]*$(?:(?!^## )[\s\S])*^```mermaid[ \t]*\n[ \t]*classDiagram\b[\s\S]*^## Collaborators[ \t]*$'
flags: m
---

Both enabled component types are written: Internals with a Mermaid
`flowchart` (`component-detail`) and Types with a `classDiagram` (`class`),
between Responsibility and Collaborators, in that order.
