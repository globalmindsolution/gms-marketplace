---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-e2e-tests/result.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"interrupted")(?=[\s\S]*"stop_reason"\s*:\s*"needs_input")'
---

"If it has none, finish `needs_input` with that question." The ledger has no
`needs_input` status -- a step that stops for the user is `interrupted` with
`stop_reason: needs_input`, the one form `post-create-e2e-tests.py` admits --
so that is what the persisted result document says. A run that wrote suites
and completed, or never finished, fails here.
