---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"development_dir"\s*:\s*"docs/changes/?"'
---

A folder answer is saved as `docs.development_dir` in `.acs/settings.json`
(team: it is asked once per repo), by `acs.py docs decide --location
development=docs/changes`.
