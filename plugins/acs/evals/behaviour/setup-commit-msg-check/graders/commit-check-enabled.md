---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"enforcement"\s*:\s*\{[\s\S]*"checks"\s*:\s*\{[^}]*"commit_message"\s*:\s*true'
---

The one non-default answer: the local commit-message check turned on. The
scaffold has no settings file, so a run that wrote nothing fails here.
