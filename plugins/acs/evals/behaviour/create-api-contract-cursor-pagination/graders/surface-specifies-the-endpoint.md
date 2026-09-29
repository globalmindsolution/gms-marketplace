---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/api-contract.md }
pattern: '^## Surface[ \t]*$(?:(?!^## )[\s\S])*^### [^\n]*customers(?:(?!^## )[\s\S])*next_cursor'
flags: m
---

`## Surface` carries a `### ` item for the endpoint the plan changes, and that
item specifies the new response field `next_cursor` (AC-2).
