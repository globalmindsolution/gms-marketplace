---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"(branch_name|commit_message|ticket_prefix)"'
match: not_contains
weight: 0.5
---

Kept formats and the untouched prefix equal their defaults, and a default is
never written. Secondary: it restates the skill's own rule.
