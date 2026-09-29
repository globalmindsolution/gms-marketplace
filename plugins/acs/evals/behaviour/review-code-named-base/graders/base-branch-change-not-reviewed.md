---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/verdict.json }
pattern: 'export\.py|API_TOKEN|exp-dummy-2f9c41d7|export_url'
match: not_contains
---

The named base scopes the changeset. `src/shop/export.py` arrived on
release/2.4 and is not in `release/2.4...HEAD`; a hard-coded token is exactly
what a review would block on, so a run that reviewed against main instead
names it here and fails. A verdict that does not exist fails too.
