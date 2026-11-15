---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"ticket_prefix"\s*:\s*"PAY"'
---

The earlier run's ticket prefix is still there. A re-run that resets it to
the default has thrown away a team decision.
