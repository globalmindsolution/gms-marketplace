---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"release"'
match: not_contains
---

"Do NOT guess a fallback shape": configuring the repo for release cuts is the
user's decision, so the settings file still carries no `release` key.
