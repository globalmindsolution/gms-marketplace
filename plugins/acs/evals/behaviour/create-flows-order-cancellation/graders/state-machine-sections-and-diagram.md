---
type: regex
target: { source: file, path: docs/architecture/lld/orders/flows/state-order.md }
pattern: '(?<![\s\S])(?=[\s\S]*^```mermaid[ \t]*\n[ \t]*stateDiagram-v2\b)[\s\S]*^## Entity[ \t]*$[\s\S]*^## States[ \t]*$[\s\S]*^## Transitions[ \t]*$[\s\S]*^## Invariants[ \t]*$'
flags: m
---

The state machine's required sections in order -- Entity, States,
Transitions, Invariants -- and a Mermaid `stateDiagram-v2` in the file.
