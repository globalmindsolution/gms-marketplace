---
type: regex
target: { source: file, path: package.json }
pattern: '"version"\s*:\s*"2\.4\.0"'
---

The configured version location still holds the released version. A bump
(by the helper or by hand) replaces it with 2.5.0.
