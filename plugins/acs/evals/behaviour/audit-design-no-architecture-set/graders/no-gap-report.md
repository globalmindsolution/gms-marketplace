---
type: regex
target: files
pattern: '/steps/audit-design/iter-\d+/gaps'
match: not_contains
---

"None -> say so and stop: there is nothing to audit." The stop comes before
any gap analyst is spawned, so no gap notes and no joined report exist. A run
that compared the code with the PRD or the README instead wrote one.
