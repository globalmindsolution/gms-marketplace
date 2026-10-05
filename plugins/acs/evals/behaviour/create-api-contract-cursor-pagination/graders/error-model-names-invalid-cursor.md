---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/api/customers.md }
pattern: '^## Error model[ \t]*$(?:(?!^## )[\s\S])*invalid_cursor'
flags: m
---

AC-3's error code, which the prompt settled, belongs in the interface's Error
model.
