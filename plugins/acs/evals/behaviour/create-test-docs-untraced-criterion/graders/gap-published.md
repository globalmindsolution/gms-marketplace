---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/test-cases.md }
pattern: '^## Gaps and assumptions[ \t]*$(?:(?!^## )[\s\S])*AC-4'
flags: m
---

"Publish the document anyway when it verified -- a document with a named gap
is what the answer comes back to": the traced cases for AC-1..AC-3 are
published, with AC-4 named as the gap.
