---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/design.md }
pattern: '^## Options considered[ \t]*$(?:(?!^## )[\s\S])*^### [^\n]+\n(?:(?!^## )[\s\S])*^### [^\n]+'
flags: m
---

At least two real options, each its own `### ` subsection -- here, carrier
webhooks versus polling.
