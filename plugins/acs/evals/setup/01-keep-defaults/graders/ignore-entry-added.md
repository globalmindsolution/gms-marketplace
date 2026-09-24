---
type: regex
target: { source: file, path: .gitignore }
pattern: '^\.acs/settings\.local\.json$'
flags: m
---

Evidence that setup actually applied, not just talked: its one write on a
keep-everything run is the ignore entry for the machine-local settings file.
