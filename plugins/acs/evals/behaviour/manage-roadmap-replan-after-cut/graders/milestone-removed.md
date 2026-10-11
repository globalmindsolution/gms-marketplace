---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?![\s\S]*2\.6\.0)(?![\s\S]*features/order-tracking/)(?=[\s\S]*\n## Release versions\n)'
---

The cut feature leaves the plan: no milestone links order tracking, and
neither its heading nor its Release versions row (v2.6.0) survives -- the
roadmap's own floor (`wont-scheduled`) refuses a Won't-have in a milestone.
