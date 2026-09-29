---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/design.md }
pattern: '^## Options considered[ \t]*$(?:(?!^## )[\s\S])*^### [^\n]+\n(?:(?!^## )[\s\S])*^### [^\n]+'
flags: m
---

At least two real options, each its own `### ` subsection under Options
considered -- the `alternatives` dimension. A design that states one answer
fails.
