---
type: regex
target: { source: file, path: docs/requirements/non-functional/performance.md }
pattern: '^(?=DRAFT\s*[—–-]+\s*human-confirm-required)(?=[\s\S]*\b2\s?(?:s|seconds?)\b)'
flags: mi
---

The performance item, DRAFT-marked, with the PRD's 2 s p95 bound.
