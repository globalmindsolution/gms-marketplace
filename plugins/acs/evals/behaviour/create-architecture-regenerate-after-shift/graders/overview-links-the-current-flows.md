---
type: regex
target: { source: file, path: docs/architecture/hld/overview.md }
pattern: '^(?![\s\S]*nightly-export)(?=[\s\S]*list-orders)(?=[\s\S]*list-customers)'
---

The overview's links to LLD flows resolve: every confirmed flow is listed and
the removed flow no longer lingers (the integration pass's seam).
