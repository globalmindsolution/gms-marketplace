---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"merge_strategy"\s*:\s*"fast-forward"'
---

A hand-set setting is the user's to fix; the umbrella writes no file, and
the user said not to change it.
