---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?=[\s\S]*\n## Release versions\n)(?=[\s\S]*\|\s*v2\.4\.0\s*\|\s*Storefront\s*\|)(?=[\s\S]*\|\s*v2\.5\.0\s*\|\s*Checkout\s*\|)(?=[\s\S]*\|\s*v2\.6\.0\s*\|\s*Order tracking\s*\|)'
---

Every milestone resolves to exactly one release version: one Release versions
row per milestone, its version and its name (0 orphan milestones).
