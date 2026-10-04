---
type: regex
target: { source: file, path: docs/architecture/lld/orders/flows/cancel-order.md }
pattern: '^```mermaid[ \t]*\n[ \t]*sequenceDiagram\b(?=(?:(?!^```)[\s\S])*^[^\n]*--?(?:>>?|x|\))[^\n]*:[^\n]*cancel)(?=(?:(?!^```)[\s\S])*^[^\n]*--?(?:>>?|x|\))[^\n]*:[^\n]*refund)'
flags: mi
---

The sequence carries the message that changes the order's state -- the
cancel request -- and, for a paid order, the refund call to the payments
gateway before it, both as Mermaid messages inside the one
`sequenceDiagram`.
