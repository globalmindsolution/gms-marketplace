---
type: regex
target: last_message
pattern: '\b1\s*(?:/|of)\s*2\b[^\n]*pass|\b1 (?:suite )?passed\W+1 (?:suite )?failed'
flags: i
---

The report states the pass count against the suites run (the completion
block's "Results: <pass count>/<N> suites passed"): one of the two passed.
A run that saw both green, or ran only one suite, reports something else.
