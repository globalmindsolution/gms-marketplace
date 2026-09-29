---
type: regex
target: { source: file, path: docs/architecture/hld/data-model.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*erDiagram)(?=[\s\S]*appointment)'
flags: i
---

The data model is designed, not extracted: a Mermaid `erDiagram` over the
entities the answers named, appointments among them.
