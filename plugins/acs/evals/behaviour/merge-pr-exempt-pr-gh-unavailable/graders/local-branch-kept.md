---
type: regex
target: { source: file, path: .git/refs/heads/hotfix/health-casing }
pattern: '^[0-9a-f]{40}'
---

Cleanup (`git branch -D`) runs only after a confirmed merge.
