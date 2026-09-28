---
type: regex
target: files
pattern: '^(\.acs|\.claude)/|(^|/)plugin\.json$'
flags: m
match: not_contains
---

No state, settings backup or manifest is left behind: "Artifacts: none".
