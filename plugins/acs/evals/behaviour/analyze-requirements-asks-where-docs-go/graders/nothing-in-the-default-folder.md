---
type: regex
target: files
pattern: '^docs/development/'
flags: m
match: not_contains
---

acs never creates a new docs folder without the user's answer (ADR-0132): with
no `docs.development_dir` and no existing folder, the built-in default
`docs/development` is only a proposal. A run that published there -- before
asking, or instead of the folder the user named -- fails here.
