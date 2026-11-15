---
type: regex
target: files
pattern: '^\.acs/settings\.local\.json$'
flags: m
match: not_contains
---

The user asked for the team's choice, not this machine's: nothing is written
to `.acs/settings.local.json` (the `user` scope), which would shadow the team
default for this checkout only.
