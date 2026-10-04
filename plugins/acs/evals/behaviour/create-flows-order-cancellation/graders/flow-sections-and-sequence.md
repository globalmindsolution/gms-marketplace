---
type: regex
target: { source: file, path: docs/architecture/lld/orders/flows/cancel-order.md }
pattern: '^## Purpose[ \t]*$[\s\S]*^## Trigger[ \t]*$[\s\S]*^## Participants[ \t]*$[\s\S]*^## Sequence[ \t]*$(?:(?!^## )[\s\S])*^```mermaid[ \t]*\n[ \t]*sequenceDiagram\b[\s\S]*^## Errors and edge cases[ \t]*$'
flags: m
---

The flow file's required sections in order -- Purpose, Trigger,
Participants, Sequence (a Mermaid `sequenceDiagram`), then, after the
optional Activity, Errors and edge cases.
