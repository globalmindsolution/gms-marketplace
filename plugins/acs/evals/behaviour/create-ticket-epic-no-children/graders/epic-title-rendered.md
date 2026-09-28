---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"title"\s*:\s*"\[EPIC\] [^"(]'
---

Step 3 renders the title from `settings.formats.tickets.epic.title`, whose
default is `[EPIC] {title}`. The placeholder `(ticket under analysis)` and an
unrendered title both fail.
