---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/code/state.json }
pattern: '"handoff_summary"\s*:\s*"[^"]{10,}'
---

`handoff.py` finalized the open invocation with the summary the next session
reads. `acs.py step finish --status interrupted` would move the step but carry
no handoff summary, so a run that finished the step some other way fails here.
