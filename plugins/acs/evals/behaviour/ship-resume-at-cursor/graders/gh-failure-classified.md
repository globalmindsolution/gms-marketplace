---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"errors"\s*:\s*\[(?:(?!"invocations")[\s\S])*\bgh\b'
---

create-pr records the critical gh failure in its result document's `errors`,
naming the gh call. The tempered match stops at `"invocations"`, so a gh
mention in derived-state provenance cannot pass it.
