---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: '"command"\s*:\s*"[^"]*pytest'
---

The gate runs a command from the committed settings, and this repo is a
pytest project. Without a command CI has nothing to run and fails every PR.
