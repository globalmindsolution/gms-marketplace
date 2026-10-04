---
type: regex
target: files
pattern: '/steps/audit-design/iter-\d+/(?:gaps|report)'
match: not_contains
---

"None -> say so and stop: there is nothing to audit." The stop comes before
`acs step start` and before any gap analyst is spawned, so no gap notes, no
joined gaps.md and no report.md (the template-shaped report the post-hook
counts) exist. A run that compared the code with the PRD or the README
instead, or filled the report template with empty sections to have something
to finish with, wrote one.
