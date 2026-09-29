---
type: regex
target: { source: file, path: pyproject.toml }
pattern: 'version = "2\.4\.0"'
---

The product's real version file still holds the released version; a bump by
hand replaces it.
