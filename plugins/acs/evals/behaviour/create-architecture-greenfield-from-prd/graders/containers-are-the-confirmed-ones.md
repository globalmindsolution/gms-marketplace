---
type: regex
target: { source: file, path: docs/architecture/hld/c4-container.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*booking-api)(?=[\s\S]*reminder-worker)(?=[\s\S]*PostgreSQL)'
---

Greenfield designs the system the answers fixed: a Mermaid container view
naming the three confirmed containers. With no code to read, a view built
from anything else (a single monolith, an invented cache) is a guess.
