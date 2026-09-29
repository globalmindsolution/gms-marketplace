---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/state.json }
pattern: '"handoff_summary"\s*:\s*"[^"]{10,}'
---

`handoff.py` finalized the open review-code invocation with the summary the
next session reads. `acs.py step finish --status interrupted` moves the step
but carries no handoff summary.
