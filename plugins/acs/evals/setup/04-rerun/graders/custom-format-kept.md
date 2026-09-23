---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"pr_title"\s*:\s*"\[\{ticket_id\}\] \{title\}"'
---

The earlier run's custom PR title is still there. A re-run that resets it to
the default has thrown away a team decision.
