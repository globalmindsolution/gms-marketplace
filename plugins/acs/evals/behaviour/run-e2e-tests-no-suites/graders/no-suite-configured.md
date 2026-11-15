---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"(?:tests|suites|e2e)"'
match: not_contains
---

The skill runs what is configured; it never configures a suite to have
something to run. The settings file still carries no `tests` (or old `suites` or `e2e`) key.
