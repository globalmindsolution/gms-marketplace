---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/merge-pr/state.json }
pattern: '"(?:errors|findings)"\s*:\s*\[(?:(?!"invocations")[\s\S])*\bgh\b'
---

The failed readiness read is recorded as a classified gh failure -- in
`errors` (where the policy puts a critical call) or as a blocking finding --
naming gh. The tempered match stops at `"invocations"`, the key after both
lists in the state file, so gh named anywhere else does not count.
