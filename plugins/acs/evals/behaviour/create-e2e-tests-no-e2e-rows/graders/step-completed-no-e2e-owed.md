---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-e2e-tests/result.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"outcome"\s*:\s*"no_e2e_owed")'
---

"`test-cases.md` lists at least one e2e case. Zero → nothing to write: finish
`completed` with `outcome: "no_e2e_owed"`." The result document, persisted by
`post-create-e2e-tests.py`, says so. `tests_written`, a failure, or no finish
at all fail here.
