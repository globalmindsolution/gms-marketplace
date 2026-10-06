---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"errors"\s*:\s*\[(?:(?!"invocations")[\s\S])*\bgh\b'
---

The failure is recorded where the policy puts a critical gh failure: in the
result document's `errors` (copied into the step state), naming the gh call.
The tempered match stops at `"invocations"`, the key that follows `errors` in
the state file, so a mention of gh elsewhere (the derived-states provenance
says "gh is not on PATH") cannot satisfy it.
