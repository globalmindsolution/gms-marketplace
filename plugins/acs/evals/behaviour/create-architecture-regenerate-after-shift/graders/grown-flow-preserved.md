---
type: regex
target: { source: file, path: docs/architecture/lld/flows/list-customers.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*sequenceDiagram)(?=[\s\S]*/customers)'
---

Re-run preserves flow files grown ticket-by-ticket unless the flow no longer
exists: list-customers still does, so its file survives the regeneration.
