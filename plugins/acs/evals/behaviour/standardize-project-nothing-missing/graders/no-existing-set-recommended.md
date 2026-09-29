---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/standardize-project/result.json }
pattern: 'create-(principles|standards|architecture)'
match: not_contains
---

All three sets exist, so none is a follow-up: an audit that recommends
bootstrapping one did not read what is there. (A missing result document
fails here too.)
