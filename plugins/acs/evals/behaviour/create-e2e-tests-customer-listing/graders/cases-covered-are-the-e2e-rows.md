---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-e2e-tests/result.json }
pattern: '"cases_covered"\s*:\s*\[(?=[^\]]*"TC-2")(?=[^\]]*"TC-3")(?![^\]]*"TC-1")[^\]]*\]'
---

The step's result document, persisted by `post-create-e2e-tests.py`, records
`cases_covered` equal to the e2e-typed rows: TC-2 and TC-3, in any order, and
never TC-1 -- a unit case the case document assigns to `tests/unit/`, which an
e2e suite covering it would duplicate. A run that never finished the step has
no result document and fails here.
