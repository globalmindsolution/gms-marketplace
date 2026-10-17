---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"ticket_prefix"\s*:\s*"PAY"'
---

The re-run leaves the configured ticket prefix as it was.
