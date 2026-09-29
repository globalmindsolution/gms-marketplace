---
type: regex
target: { source: file, path: .git/hooks/commit-msg }
pattern: 'check-conventions\.py[\s\S]*--mode commit-msg'
---

The clone's commit-msg hook runs the committed checker on every commit
subject. The scaffold has no commit-msg hook, so a run that installed nothing
fails here (the file does not exist).
