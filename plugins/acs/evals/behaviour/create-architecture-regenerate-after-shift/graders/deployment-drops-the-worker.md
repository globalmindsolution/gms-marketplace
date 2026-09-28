---
type: regex
target: { source: file, path: docs/architecture/hld/deployment.md }
pattern: '^(?![\s\S]*(?:redis|export.worker))(?=[\s\S]*```mermaid)'
flags: i
---

The deployment view matches the real topology after the shift: no
export-worker and no Redis.
