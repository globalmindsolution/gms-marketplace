---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/test-cases.md }
pattern: '^(?=.*\|[ \t]*TC-\d+[ \t]*\|[^\n]*\bAC-1\b)(?=.*\|[ \t]*TC-\d+[ \t]*\|[^\n]*\bAC-2\b)(?=.*\|[ \t]*TC-\d+[ \t]*\|[^\n]*\bAC-3\b)'
flags: s
---

`## Cases` is a table whose first column is `TC-<n>`, and every criterion --
numbered AC-1..AC-3 by position, the trace key the pipeline uses -- appears on
at least one TC row. `untraced_acs` must be empty on a completed run.
