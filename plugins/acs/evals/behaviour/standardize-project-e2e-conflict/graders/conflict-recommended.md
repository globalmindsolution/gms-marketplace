---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json }
pattern: '"recommended_follow_ups"\s*:\s*\[[^\]]*acs-e2e'
---

"The conflict becomes a `recommended_follow_ups` entry instead of an
in-place modification": an entry naming the acs-e2e.yml conflict in the
leg's result document. A run that never reached Finish has no result.json;
one that silently skipped the conflict records no such entry.
