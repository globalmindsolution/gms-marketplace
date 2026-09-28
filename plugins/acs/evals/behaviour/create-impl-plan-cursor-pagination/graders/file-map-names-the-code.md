---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/plan.md }
pattern: '^## Contract[ \t]*$(?:(?!^## )[\s\S])*^### Executor tasks & file map[ \t]*$(?:(?!^## )[\s\S])*src/shop/__init__\.py'
flags: m
---

`### Executor tasks & file map` keeps its exact heading inside the Contract
block because the file-map guard and `plan-approval.py` key on it, and it must
name the file the change lives in: `list_customers` is in
`src/shop/__init__.py`.
