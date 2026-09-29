---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/state.json }
pattern: '"verifier_passed"\s*:\s*true'
---

`verifier_passed` is DERIVED by review-code's post-hook from the verdict the
review wrote -- no skill can assert it. True means the change passed a real
review before ship moved on, and it is the brake create-pr checks.
