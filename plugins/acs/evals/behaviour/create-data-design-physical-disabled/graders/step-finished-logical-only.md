---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-data-design/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/orders/data/logical-erd\.md")(?=[\s\S]*"types"\s*:\s*\[\s*"logical-erd"\s*\])'
---

The Finish ran through the post-hook (`completed`), `states.files` lists the
logical ERD it wrote, and `states.types` -- the owned types written -- is
exactly `["logical-erd"]`: the disabled physical-schema is neither written
nor claimed.
