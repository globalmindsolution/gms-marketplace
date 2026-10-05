---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/verdict.json }
pattern: 'page_bounds|off[- ]by[- ]one|0-based|zero-based|first page|page \* per_page|\(page - 1\)'
flags: i
---

The blocking finding is about the seeded defect: `page_bounds` documents
1-based pages and computes `start = page * per_page`, so page 1 skips the first
page. A verdict whose only finding is about something else (the docs, style)
names none of these.
