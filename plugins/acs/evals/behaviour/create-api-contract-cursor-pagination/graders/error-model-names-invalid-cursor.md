---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/api-contract.md }
pattern: '^## Error model[ \t]*$(?:(?!^## )[\s\S])*invalid_cursor'
flags: m
---

AC-3's error code, which the prompt settled, belongs in the Error model.
