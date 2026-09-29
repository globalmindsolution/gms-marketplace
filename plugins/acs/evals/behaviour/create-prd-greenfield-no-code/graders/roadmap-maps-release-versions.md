---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^(?=[\s\S]*Release versions)(?=[\s\S]*\bv?0\.1\.0\b)(?=[\s\S]*\bv?0\.2\.0\b)(?=[\s\S]*Booking MVP)(?=[\s\S]*Deposits)'
flags: i
---

The roadmap maps the two stated milestones to their stated versions in the
"Release versions" table the skill requires.
