---
type: regex
target: { source: file, path: docs/architecture/lld/orders/flows/state-order.md }
pattern: '^```mermaid[ \t]*\n[ \t]*stateDiagram-v2\b(?=(?:(?!^```)[\s\S])*^[ \t]*placed[ \t]*-->[ \t]*cancelled[ \t]*:[^\n]*cancel)(?=(?:(?!^```)[\s\S])*^[ \t]*paid[ \t]*-->[ \t]*cancelled[ \t]*:[^\n]*cancel)(?!(?:(?!^```)[\s\S])*^[ \t]*(?:shipped|delivered)[ \t]*-->[ \t]*cancelled\b)'
flags: mi
---

Sequence and state agree: the cancel message in the flow changes the order's
state, so the state machine has that transition, labelled with the message
that triggers it -- `placed --> cancelled` and `paid --> cancelled`, each
naming the cancel request -- and, per the third criterion, no transition
from shipped or delivered to cancelled. A state machine that copies the
code's placed -> paid -> shipped -> delivered lifecycle and stops misses
what the flow implies.
