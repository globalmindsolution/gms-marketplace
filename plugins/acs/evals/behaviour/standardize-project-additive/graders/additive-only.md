---
type: regex
target: files
pattern: '^(src|tests|docs)/'
flags: m
match: not_contains
---

The additive-surface allowlist is CI workflows and tooling config. A new file
under src/ or tests/ is source the leg may not write, and one under docs/ is
a principles/standards set it must recommend, never author.
