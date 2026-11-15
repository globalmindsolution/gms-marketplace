---
type: regex
target: { source: file, path: docs/architecture/hld/integration-map.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*flowchart)(?=[\s\S]*customers)(?=[\s\S]*health)'
flags: i
---

Grounded in the codebase: the API landscape is a Mermaid `flowchart` naming
the two APIs `shop` really exposes, the customer listing and the health probe
(src/shop/__init__.py, README.md). A landscape written from the PRD alone
describes checkout and payments and never these.
