---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?![\s\S]*2\.6\.0)(?=[\s\S]*Release versions)(?=[\s\S]*\|\s*v2\.5\.0\s*\|\s*Checkout\s*\|)'
---

The roadmap is updated only where the amendment changes it: the Order
tracking milestone and its v2.6.0 release row are gone, the Release versions
table and the Checkout v2.5.0 row stay.
