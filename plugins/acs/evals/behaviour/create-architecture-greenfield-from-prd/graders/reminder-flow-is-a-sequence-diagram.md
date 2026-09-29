---
type: regex
target: { source: file, path: docs/architecture/lld/flows/send-reminder.md }
pattern: '^(?=[\s\S]*```mermaid)(?=[\s\S]*sequenceDiagram)(?=[\s\S]*reminder-worker)(?=[\s\S]*SMS)'
---

Each flow file is a Mermaid `sequenceDiagram` whose participants are the
container vocabulary the HLD pins: the reminder flow runs from
reminder-worker to the external SMS gateway.
