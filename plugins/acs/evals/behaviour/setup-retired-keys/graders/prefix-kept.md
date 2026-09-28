---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"ticket_prefix"\s*:\s*"EVAL"'
---

A re-run is safe by construction: the one live setting the file carries
survives it.
