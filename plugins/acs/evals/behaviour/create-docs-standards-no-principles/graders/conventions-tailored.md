---
type: regex
target: { source: file, path: docs/standards/conventions.md }
pattern: '^(?=[\s\S]*^#{1,3}\s+Naming conventions)(?=[\s\S]*^#{1,3}\s+Formatting)(?=[\s\S]*snake_case)(?=[\s\S]*\b100\b)(?=[\s\S]*\bruff\b)'
flags: mi
---

Tailored to the confirmed conventions: snake_case naming, the 100-character
line, ruff. None of them is in the template.
