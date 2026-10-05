---
type: regex
target: files
pattern: '^\.acs/settings\.local\.json$'
flags: m
match: not_contains
---

The default was saved already; nothing is asked and nothing re-saved. A run
that asked anyway and recorded the answer for this machine creates
`.acs/settings.local.json` and fails here.
