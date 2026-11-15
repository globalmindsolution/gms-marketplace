---
type: regex
target: { source: file, path: docs/architecture/lld/checkout-with-card-payments/EVAL-1/tech-design.md }
pattern: '^### Options considered[ \t]*$(?:(?!^##?#? )[\s\S])*^#### [^\n]+\n(?:(?!^##?#? )[\s\S])*^#### [^\n]+'
flags: m
---

At least two real options, each its own `#### ` subsection under
`### Options considered` in Decision & options -- the `alternatives`
dimension. A design that states one answer fails.
