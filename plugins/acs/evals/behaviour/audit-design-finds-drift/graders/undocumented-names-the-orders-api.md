---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/audit-the-design-against-the-code-9784/steps/audit-design/iter-1/gaps.md }
pattern: '## Undocumented\n(?:(?!\n## )[\s\S])*orders'
flags: i
---

The orders API (GET /orders?customer_id=, src/shop/orders.py) is built and no
in-scope document shows it: `## Undocumented`.
