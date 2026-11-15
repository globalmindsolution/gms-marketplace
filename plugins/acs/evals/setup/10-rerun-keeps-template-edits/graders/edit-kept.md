---
type: regex
target: { source: file, path: .acs/templates/prd-feature-default.md }
pattern: '^##\s+Rollout\s*$'
flags: m
---

The team's edit is theirs: setup's re-run never overwrites a customised copy,
so the feature PRD template still carries its `## Rollout` section.
