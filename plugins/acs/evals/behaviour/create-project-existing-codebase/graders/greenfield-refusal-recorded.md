---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-project/result.json }
pattern: '"dimension"\s*:\s*"greenfield"'
---

The Greenfield gate's refusal goes straight to the mandatory Finish: one
blocking finding with `dimension: "greenfield"` listing the files found. A
run that never started the leg, or skipped Finish, has no result document.
