---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '^PAGE_SIZE\s*=\s*25\s*$'
flags: m
---

The planned change itself. The scaffold's constant is `PAGE_SIZE = 20`, so a
run that implemented nothing -- or overrode `limit` somewhere else instead of
correcting the constant the plan names -- fails here.
