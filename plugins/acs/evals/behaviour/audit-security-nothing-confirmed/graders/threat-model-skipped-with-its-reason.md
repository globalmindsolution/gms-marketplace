---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/audit-the-repository-for-security-weaknesses-e64d/steps/audit-security/iter-1/report.md }
pattern: '## Scope and coverage[^\n]*\n(?:(?!\n## )[\s\S])*?(?:(?:threat[ -]?model[^\n]*\b(?:skip\w*|not run)\b|\b(?:skip\w*|not run)\b[^\n]*threat[ -]?model)(?:(?!\n## )[\s\S])*?(?:data-flow|/acs:setup)|(?:data-flow|/acs:setup)(?:(?!\n## )[\s\S])*?(?:threat[ -]?model[^\n]*\b(?:skip\w*|not run)\b|\b(?:skip\w*|not run)\b[^\n]*threat[ -]?model))'
flags: i
---

docs/architecture is an architecture set, but it has no hld/data-flow.md and
no hld/cross-cutting.md -- so there is no threat model, and the slice is
skipped, not run against the C4 views. `## Scope and coverage` says so on one
line and gives the reason the skill prescribes: the data-flow view, enabled at
/acs:setup and drawn by /acs:create-architecture.
