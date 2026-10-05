---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"title"\s*:\s*"\[EPIC\] [^"(]'
---

Step 3 sets the title: an epic's title is prefixed `[EPIC] `. The placeholder `(ticket under analysis)` and an
unrendered title both fail.
