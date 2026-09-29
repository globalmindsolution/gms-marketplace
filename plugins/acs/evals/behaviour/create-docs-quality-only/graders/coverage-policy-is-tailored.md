---
type: regex
target: { source: file, path: docs/quality/coverage-policy.md }
pattern: '^(?=[\s\S]*^#{1,3}\s+Target and hard-fail rule)(?=[\s\S]*\b90\s?%)(?=[\s\S]*pytest)'
flags: mi
---

Bootstrapped from the template AND tailored: the template's headings are
there, and the body states the PRD's 90% target and the stack's pytest
tooling. The untailored template carries neither, only HTML comments.
