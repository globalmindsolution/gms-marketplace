---
type: regex
target: { source: file, path: docs/architecture/hld/c4-component.md }
pattern: '^(?![\s\S]*export.worker)(?=[\s\S]*```mermaid)(?=[\s\S]*orders)'
flags: i
---

Re-run mode updates content in place: the component view gains the orders
component the latest commit added and drops the removed export worker. The
scaffold's version names the worker and no orders, so a run that left the
file alone fails here.
