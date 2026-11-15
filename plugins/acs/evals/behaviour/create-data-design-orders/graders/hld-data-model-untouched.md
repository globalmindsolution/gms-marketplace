---
type: regex
target: { source: file, path: docs/architecture/hld/data-model.md }
pattern: '(?<![\s\S])# Data model\n\nConceptual entities and relationships; attributes live in the low-level\ndata design of each feature\.\n\n```mermaid\nerDiagram\n  CUSTOMER \|\|--o\{ ORDER : places\n  ORDER \|\|--\|\{ ORDER_LINE : contains\n  PRODUCT \|\|--o\{ ORDER_LINE : "is ordered as"\n```\n(?![\s\S])'
---

The HLD's conceptual model is an input this design details, never an output:
byte for byte as the scaffold left it. Attributes belong in the feature's
logical ERD; a change to the conceptual model is /acs:create-architecture's.
