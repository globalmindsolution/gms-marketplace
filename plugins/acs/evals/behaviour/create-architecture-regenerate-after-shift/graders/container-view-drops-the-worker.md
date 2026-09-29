---
type: regex
target: { source: file, path: docs/architecture/hld/c4-container.md }
pattern: '^(?![\s\S]*(?:redis|export.worker))(?=[\s\S]*```mermaid)(?=[\s\S]*\bshop\b)'
flags: i
---

Re-run mode keeps the same file set and updates content in place: the
container view is still a Mermaid diagram of `shop`, and the removed
export-worker container and its Redis queue are gone from it. The scaffold's
version names both, so a run that left the file alone fails here.
