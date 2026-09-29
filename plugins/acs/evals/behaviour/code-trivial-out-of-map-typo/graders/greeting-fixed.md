---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '"Hello, %s!"|"Hello, "|f"Hello, \{'
---

The red test made green in the mapped module: `greeting()` spells "Hello". A
run that did nothing, or rewrote the test to expect "Helo", leaves the
scaffold's `"Helo, %s!"` here and fails.
