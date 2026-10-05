---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-e2e-tests/result.json }
pattern: '"cases_covered"\s*:\s*\[(?=[^\]]*"AC-1")(?=[^\]]*"AC-2")(?![^\]]*"TC-)[^\]]*\]'
---

On the acceptance-criteria fallback "each derived case carries the acceptance
criterion it proves (`AC-<n>`) wherever this file says `TC-<n>`", so the
persisted `cases_covered` names AC-1 and AC-2 -- and no invented `TC-` id, which
would pretend a case document existed.
