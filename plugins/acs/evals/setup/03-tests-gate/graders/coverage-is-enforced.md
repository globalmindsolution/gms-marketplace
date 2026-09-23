---
type: regex
target: { source: file, path: .acs/settings.json }
pattern: 'ACS_COVERAGE|cov-fail-under'
weight: 0.5
---

A coverage gate whose command never fails below the target enforces nothing.
Secondary: `$ACS_COVERAGE` is the skill's own name for the target.
