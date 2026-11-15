---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"(?:analyze-requirements|create-impl-plan|create-test-docs|code|review-code|create-e2e-tests|docs-sync|run-e2e-tests)"\s*:\s*\{\s*"status"\s*:\s*"completed"'
match: count:8
---

The run's ledger still records the eight steps before create-pr `completed`:
resuming neither resets them nor re-opens one (a re-opened step reads
`in_progress` or `failed` until it finishes again).
