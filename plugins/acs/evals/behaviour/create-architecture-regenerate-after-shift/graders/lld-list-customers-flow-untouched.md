---
type: regex
target: { source: file, path: docs/architecture/lld/flows/list-customers.md }
pattern: '^# list-customers\n\n```mermaid\nsequenceDiagram\n  participant Shopper\n  participant shop\n  Shopper->>shop: GET /customers\?offset=0&limit=20\n  shop-->>Shopper: page of customers\n```\n(?![\s\S])'
---

A flow file grown ticket by ticket is low-level design the regeneration does
not own: the still-valid list-customers flow is left exactly as the scaffold
wrote it, not rewritten in the HLD's new vocabulary.
