---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/test-cases.md }
pattern: '^e2e_cases: 0$(?![\s\S]*\|\s*e2e\s*\|)'
flags: m
---

"Do NOT work around this by editing `test-cases.md` yourself." The front
matter still declares zero e2e cases and no row is retyped `e2e`.
