---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"(?:analyze-requirements|create-impl-plan|create-test-docs|code|review-code|create-e2e-tests|docs-sync|run-e2e-tests)"\s*:\s*\{\s*"status"\s*:\s*"completed"'
match: count:8
---

The run's own ledger, written by each step's post-hook (or, for a step that
owes nothing, by its pre-hook's evidenced no-op): every step ship.yaml lists
before create-pr is `completed`. Eight keys in a map, so exactly eight matches (create-api-contract left the
pipeline for Design, ADR-0134).
A ship that stopped early, skipped a step, or ran the steps without their
hooks has fewer.
