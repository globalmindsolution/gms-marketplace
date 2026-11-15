---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?=[\s\S]*### Checkout — v2\.5\.0\n\n- Status: delivered\n)(?=[\s\S]*\| v2\.5\.0 \| Checkout \| EVAL-1 \| delivered \|)'
---

Checkout's one tracked ticket, EVAL-1, leads a commit subject on the default
branch, so its derived status is `delivered` -- in its Status line and in its
Release versions cell alike.
