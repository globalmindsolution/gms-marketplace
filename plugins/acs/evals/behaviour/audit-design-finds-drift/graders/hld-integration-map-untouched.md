---
type: regex
target: { source: file, path: docs/architecture/hld/integration-map.md }
pattern: '^-{3}\nstatus: "implemented"\nversion: 1\ntickets:\n  - "EVAL-1"\n-{3}\n\n# Integration map\n\n```mermaid\nflowchart LR\n  lb\[load balancer\] -->\|GET /health sync\| shop\n  client\[shopper client\] -->\|GET /customers sync\| shop\n  shop -->\|POST /notifications sync\| notifier\n```\n(?![\s\S])'
---

Read-only: the integration map keeps its stale POST /notifications edge and
misses the orders API exactly as before the run. Adding the undocumented
API to it is a design change the report hands on, never one the audit
makes.
