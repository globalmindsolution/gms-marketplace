---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"errors"\s*:\s*\[(?:(?!"invocations")[\s\S])*\bgh\b'
---

A critical GitHub failure with no working route is recorded in the result
document's `errors`, naming the gh call. The tempered match stops at
`"invocations"` so a mention of gh elsewhere in the state file cannot satisfy it.
