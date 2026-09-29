---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/test-cases.md }
pattern: '^\|[ \t]*TC-\d+[ \t]*\|[^|\n]*\|[ \t]*e2e[ \t]*\|'
flags: mi
---

The HTTP criteria are e2e cases, and the third column -- Type -- is EXACTLY
the bare word `e2e`: the gate counts a row only then. `` `e2e` `` in
backticks or "e2e (smoke)" silently counts zero and the e2e step is skipped.
