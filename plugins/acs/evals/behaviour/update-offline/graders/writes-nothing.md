---
type: regex
target: files
pattern: '^\.acs/|(^|/)plugin\.json$|(^|/)settings(\.local)?\.json$'
flags: m
match: not_contains
---

"Artifacts: none (this skill writes nothing)". An update check that leaves
state, a settings file or a plugin manifest behind has done something it
does not own.
