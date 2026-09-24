---
type: regex
target: files
pattern: 'acs-(tests|e2e)\.yml|(^|/)\.acs/ci/run-'
flags: m
match: not_contains
---

"I don't want to change anything": no gate that was not already installed.
