---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/test-cases.md }
pattern: '^\|[ \t]*TC-\d+[ \t]*\|[^|\n]*\bAC-4\b'
flags: m
match: not_contains
---

"Do NOT invent a case that only appears to cover it": no TC row may claim
AC-4 (a lint run, a complexity threshold nobody asked for). The file must
exist for this to pass.
