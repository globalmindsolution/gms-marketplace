---
type: regex
target: { source: file, path: package.json }
pattern: '"version"\s*:\s*"2\.4\.0"'
---

The manifest still holds the released version; a hand bump replaces it.
