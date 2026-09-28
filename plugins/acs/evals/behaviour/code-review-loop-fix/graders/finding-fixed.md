---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: '\(\s*page\s*-\s*1\s*\)\s*\*\s*per_page|per_page\s*\*\s*\(\s*page\s*-\s*1\s*\)'
---

F-1-1's `resolved_when`: `page_bounds(1, n) == (0, n)`. The scaffold's
committed line is `start = page * per_page`; a fix computes the start from
`page - 1`. A run that disputed the finding, or did nothing, fails here.
