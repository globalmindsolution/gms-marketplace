---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan/plan-approval.json }
pattern: '"plan_sha256"\s*:\s*"ff9781e58f6ae59b80fc31dac5fe772f1a15a1e5d457299b4e3ae5e96bb98ad7"'
---

The approval record still hashes the bytes the human approved (the scaffold
asserts this digest before it edits the plan). `acs.py plan check` on the
edited plan rewrites the record with the edited plan's digest -- re-approving
an edit nobody approved -- and fails here.
