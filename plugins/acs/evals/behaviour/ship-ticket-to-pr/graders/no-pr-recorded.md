---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/state.json }
pattern: '"pr"\s*:\s*\{'
match: not_contains
---

No PR exists, so none is recorded: a pr object here would open /acs:merge-pr's
gate on a PR nobody confirmed live.
