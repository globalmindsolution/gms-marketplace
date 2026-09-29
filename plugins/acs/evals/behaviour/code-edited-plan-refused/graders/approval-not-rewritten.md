---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-impl-plan/plan-approval.json }
pattern: '"plan_sha256"\s*:\s*"8e1495b68a253b3ba0390f433efee5c2e96f1ca654af963faf4f9454e7ebac22"'
---

The approval record still hashes the bytes the human approved (the scaffold
asserts this digest before it edits the plan). `acs.py plan check` on the
edited plan rewrites the record with the edited plan's digest -- re-approving
an edit nobody approved -- and fails here.
