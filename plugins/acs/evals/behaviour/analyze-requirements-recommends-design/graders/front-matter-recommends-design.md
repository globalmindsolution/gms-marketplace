---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/analysis.md }
pattern: '^---\n(?:[a-z_]+:[^\n]*\n)*needs_design_recommendation:[ \t]*true[ \t]*\n(?:[a-z_]+:[^\n]*\n)*---'
---

The recommendation is part of the machine-read front matter, and it must
agree with the flag the run applied.
