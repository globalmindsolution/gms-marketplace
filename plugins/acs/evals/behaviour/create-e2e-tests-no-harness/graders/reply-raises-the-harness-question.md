---
type: regex
target: last_message
pattern: '(?:harness|runner|e2e (?:suite|command|location)|suites\.e2e)[^\n]*\?|needs_input'
flags: i
---

The report carries the open question -- which harness/command runs the e2e
suites, and where they live -- or names the needs_input stop.
