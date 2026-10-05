---
type: regex
target: files
pattern: '^docs/development/checkout-with-card-payments/EVAL-1/(?:analysis\.md$|analysis/(?:[Ii][Nn][Dd][Ee][Xx]\.md$|[^/\n]+/))'
flags: m
match: not_contains
---

The folder's entry file is README.md, never `index.md`; it holds no
subfolder; and the analysis is no longer one long `analysis.md` beside it
(ADR-0133).
