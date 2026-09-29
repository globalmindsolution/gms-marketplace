---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"commit_message"\s*:\s*"\{ticket_id\}: \{summary\}"[\s\S]*"checks"\s*:\s*\{[^}]*"commit_message"\s*:\s*true'
---

The team's formats and its enabled commit-message check are what the hooks
enforce, so they stay exactly as /acs:setup wrote them. A run that "fixed"
the colon format back to the default, or turned the check off to get a
clean verification, changed what the hooks enforce.
