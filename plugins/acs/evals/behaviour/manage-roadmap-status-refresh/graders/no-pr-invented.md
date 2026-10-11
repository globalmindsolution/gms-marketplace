---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/refresh-the-roadmap-status-45d8/steps/manage-roadmap/result.json }
pattern: '/pull/[0-9]+'
match: not_contains
---

The skill opens no PR (ADR-0127): the roadmap stays local for
`/acs:create-pr`, so the result document carries no PR URL. A missing
result.json means the mandatory Finish never ran, and fails here too.
