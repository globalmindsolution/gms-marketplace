---
type: regex
target: last_message
pattern: '\b([1-9])\s*(?:/|of)\s*\1\b[^\n]*pass'
flags: i
---

The report states the pass count against the suites run ("Results: <pass
count>/<N> suites passed") and they are equal: every suite that ran passed.
