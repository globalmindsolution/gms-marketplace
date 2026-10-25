---
type: regex
target: { source: file, path: docs/architecture/hld/deployment.md }
pattern: '^(?=[\s\S]*```mermaid)(?![\s\S]*```mermaid(?:(?!```)[\s\S])*(?:redis|export.worker))'
flags: i
---

The deployment view matches the real topology after the shift: no
export-worker and no Redis.

Only the diagram is checked: prose that says the worker and Redis are gone
("There is no worker, Redis or queue") states the shift, not the old topology.
