---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/design-the-groomr-architecture-a90a/steps/create-architecture/result.json }
pattern: '/pull/[0-9]+'
match: not_contains
---

The skill opens no PR (ADR-0127): its documents stay local for
`/acs:create-pr`, so the result document carries no PR URL. A missing
result.json means the mandatory Finish never ran, and fails here too.
