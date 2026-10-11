---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?=[\s\S]*\n## Milestones\n)(?=[\s\S]*\n###\s+Storefront\s+[—–-]\s+v2\.4\.0\n)(?=[\s\S]*\n###\s+Checkout\s+[—–-]\s+v2\.5\.0\n)(?=[\s\S]*\n###\s+Order tracking\s+[—–-]\s+v2\.6\.0\n)(?![\s\S]*###[^\n]*Saved carts)'
---

The three stated milestones, each a `###` heading under `## Milestones`
ending in its release version (roadmap-shape.md) -- and no milestone for
saved carts, which the user left unscheduled.
