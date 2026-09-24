---
type: regex
target: { source: file, path: .gitignore }
pattern: '^\.acs/state-machine/$'
flags: m
match: "count:1"
---

Re-running must not append a second copy of an ignore entry already present.
