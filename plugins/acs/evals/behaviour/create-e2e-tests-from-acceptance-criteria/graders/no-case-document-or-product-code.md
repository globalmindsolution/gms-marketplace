---
type: regex
target: files
pattern: '(?:^|/)test-cases\.md$|^src/[^\n]*\.py$'
flags: m
match: not_contains
---

The skill writes suites only. Writing the missing `test-cases.md` itself is
`/acs:create-test-docs`'s job, and a new module under `src/` is product code.
(Coarse: `files` sees created paths, not an edit to `web.py`.)
