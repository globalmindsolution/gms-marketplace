---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: 'if offset < 0:\n        raise ValueError\("offset must be >= 0"\)'
---

/acs:review-code is read-only. The guard the changeset wrote is still
there, as written.
