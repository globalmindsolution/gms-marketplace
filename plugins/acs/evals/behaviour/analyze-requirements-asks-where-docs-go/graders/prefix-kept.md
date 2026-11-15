---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"ticket_prefix"\s*:\s*"EVAL"'
---

`docs decide` merges into the settings file and never touches another key. A
run that hand-wrote the file and dropped the ticket prefix fails here.
